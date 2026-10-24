"""Real PostgreSQL regressions in an automatically removed, network-isolated container.
Never reads DATABASE_URL, Supabase credentials, or any remote database.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import time
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
SESSION = '00000000-0000-4000-8000-000000000001'


class AwardEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.container = 'belem-test-' + uuid.uuid4().hex[:12]
        # Pin the tested image manifest; no published ports or production volumes.
        image = 'postgres:17@sha256:b8faeff7712663c2773a190181e1246e37e364b887611c04658c28b44e2408fe'
        subprocess.run(['docker','run','--detach','--name',cls.container,'--network','none',
            '--tmpfs','/var/lib/postgresql/data','-e','POSTGRES_HOST_AUTH_METHOD=trust',image],
            check=True,capture_output=True,text=True)
        cls.addClassCleanup(lambda:subprocess.run(['docker','rm','-f',cls.container],
                                                 check=True,capture_output=True))
        for _ in range(100):
            # The image first starts a temporary server during initialization.
            # Wait for the final PostgreSQL process (PID 1), then test readiness.
            process=subprocess.run(['docker','exec',cls.container,'cat','/proc/1/comm'],
                                   capture_output=True,text=True)
            check=subprocess.run(['docker','exec',cls.container,'pg_isready','-U','postgres'],capture_output=True)
            if process.stdout.strip()=='postgres' and check.returncode==0:break
            time.sleep(.2)
        else:raise RuntimeError('Disposable PostgreSQL failed to become ready')
        cls.sql('CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role BYPASSRLS;')
        cls.sql((ROOT/'supabase/schema.sql').read_text())
        cls.sql((ROOT/'supabase/award-engine.sql').read_text())
        cls.initial_enabled=cls.sql('SELECT enabled FROM campaign_control;').stdout.strip()
        # Test-only deterministic seeds exercise the existing probability bands.
        cls.sql('''CREATE SCHEMA audit;
          CREATE FUNCTION audit.seed_for(lo float8, hi float8) RETURNS void LANGUAGE plpgsql AS $$
          DECLARE s float8; r float8;
          BEGIN
            FOR i IN 0..100000 LOOP
              s:=i/50000.0-1; PERFORM setseed(s); r:=random();
              IF r>=lo AND r<hi THEN PERFORM setseed(s); RETURN; END IF;
            END LOOP;
            RAISE EXCEPTION 'No seed found';
          END $$;''')

    @classmethod
    def command(cls):
        return ['docker','exec','-i',cls.container,'psql','-U','postgres','-X','-qAt','-v','ON_ERROR_STOP=1']

    @classmethod
    def sql(cls, statement, ok=True):
        result=subprocess.run(cls.command(),input=statement,text=True,capture_output=True,timeout=30)
        if ok and result.returncode:
            raise AssertionError(result.stderr)
        return result

    def setUp(self):
        self.sql('''TRUNCATE public.campaign_awards,public.campaign_events;
            UPDATE public.campaign_prizes SET claimed=0;
            UPDATE public.campaign_control SET enabled=true,spins_total=0;''')

    def issue(self, session=SESSION, source='direto', prefix=''):
        # Fixture values only. No live identifiers or external connections.
        return self.sql(prefix+f"SELECT * FROM public.issue_campaign_award('{session}','{source}');")

    def test_campaign_defaults_disabled(self):
        self.assertEqual(self.initial_enabled,'f')
        self.sql('UPDATE public.campaign_control SET enabled=false;')
        result=self.sql(f"SELECT * FROM public.issue_campaign_award('{SESSION}','direto');",ok=False)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Campanha ainda não ativada',result.stderr)
        self.assertEqual(self.sql('SELECT count(*) FROM campaign_awards;').stdout.strip(),'0')

    def test_sequential_retry_returns_one_coupon_and_one_stock_change(self):
        one=self.issue().stdout.strip();two=self.issue().stdout.strip()
        self.assertEqual(one,two)
        self.assertEqual(self.sql('SELECT count(*),count(DISTINCT coupon_code) FROM campaign_awards;').stdout.strip(),'1|1')
        self.assertEqual(self.sql('SELECT spins_total FROM campaign_control;').stdout.strip(),'1')
        self.assertEqual(self.sql('SELECT sum(claimed) FROM campaign_prizes;').stdout.strip(),'1')

    def test_same_session_concurrent_retry_is_idempotent(self):
        holder=subprocess.Popen(self.command(),stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,text=True,bufsize=1)
        try:
            holder.stdin.write('BEGIN; SELECT 1 FROM campaign_control WHERE id=true FOR UPDATE;\n')
            holder.stdin.flush()
            self.assertEqual(holder.stdout.readline().strip(),'1')
            with ThreadPoolExecutor(max_workers=2) as pool:
                statement=f"SELECT * FROM issue_campaign_award('{SESSION}','direto');"
                pending=[pool.submit(self.sql,statement,False) for _ in range(2)]
                try:
                    # Both calls must actually be waiting on the same control row.
                    for _ in range(100):
                        n=self.sql("SELECT count(*) FROM pg_stat_activity WHERE wait_event_type='Lock' AND query LIKE 'SELECT * FROM issue_campaign_award%';").stdout.strip()
                        if n=='2':break
                        time.sleep(.02)
                    else:self.fail('Both concurrent requests did not reach the lock')
                finally:
                    holder.stdin.write('COMMIT;\n\\q\n');holder.stdin.flush()
                results=[job.result(timeout=30) for job in pending]
            self.assertEqual([r.returncode for r in results],[0,0], [r.stderr for r in results])
            self.assertEqual(results[0].stdout,results[1].stdout)
            self.assertEqual(self.sql('SELECT spins_total FROM campaign_control;').stdout.strip(),'1')
            self.assertEqual(self.sql('SELECT count(*) FROM campaign_awards;').stdout.strip(),'1')
        finally:
            holder.communicate(timeout=5)

    def test_existing_coupon_can_be_recovered_while_distribution_paused(self):
        existing=self.issue().stdout
        self.sql('UPDATE campaign_control SET enabled=false;')
        self.assertEqual(self.issue().stdout,existing)

    def test_expired_coupon_not_reissued_or_restored_to_stock(self):
        self.issue()
        self.sql("UPDATE campaign_awards SET expires_at=clock_timestamp()-interval '1 second';")
        result=self.sql(f"SELECT * FROM issue_campaign_award('{SESSION}','direto');",ok=False)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Cupom expirado',result.stderr)
        self.assertEqual(self.sql('SELECT count(*) FROM campaign_awards;').stdout.strip(),'1')
        self.assertEqual(self.sql('SELECT sum(claimed) FROM campaign_prizes;').stdout.strip(),'1')

    def test_redeemed_coupon_cannot_be_reissued(self):
        self.issue()
        self.sql("UPDATE campaign_awards SET status='redeemed',redeemed_at=clock_timestamp();")
        result=self.sql(f"SELECT * FROM issue_campaign_award('{SESSION}','direto');",ok=False)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Cupom já utilizado',result.stderr)
        self.assertEqual(self.sql('SELECT count(*) FROM campaign_awards;').stdout.strip(),'1')

    def test_all_prizes_have_existing_expiry_and_limits(self):
        limits=self.sql('SELECT id,total FROM campaign_prizes ORDER BY id;').stdout.strip()
        self.assertEqual(limits,'10|50\n20|10\n5|\n50|3\nensaio|1')
        for i,(prize,lo,hi,hours) in enumerate([
                ('ensaio',0,.001,2),('50',.001,.004,2),('20',.004,.02,24),
                ('10',.02,.12,24),('5',.12,1,24)],start=1):
            with self.subTest(prize=prize):
                self.sql('UPDATE campaign_control SET spins_total=100;')
                prefix=f'SELECT audit.seed_for({lo},{hi});'
                session=f'00000000-0000-4000-8000-{i:012d}'
                self.issue(session,prefix=prefix)
                row=self.sql(f"SELECT prize_id,round(extract(epoch FROM (expires_at-issued_at))/3600) FROM campaign_awards WHERE session_id='{session}';").stdout.strip()
                self.assertEqual(row,f'{prize}|{hours}')

    def test_exhausted_prizes_fall_back_to_five_percent(self):
        self.sql("UPDATE campaign_prizes SET claimed=total WHERE total IS NOT NULL; UPDATE campaign_control SET spins_total=100;")
        result=self.issue(prefix='SELECT audit.seed_for(0,.001);')
        self.assertTrue(result.stdout.strip().startswith('5|'),result.stdout)
        self.assertEqual(self.sql("SELECT sum(claimed-total) FROM campaign_prizes WHERE total IS NOT NULL;").stdout.strip(),'0')

    def test_progressive_thresholds_preserved(self):
        self.assertTrue(self.issue(prefix='SELECT audit.seed_for(0,.001);').stdout.strip().startswith('5|'))
        self.sql('UPDATE campaign_control SET spins_total=4;')
        self.assertTrue(self.issue('00000000-0000-4000-8000-000000000002',prefix='SELECT audit.seed_for(0,.001);').stdout.strip().startswith('10|'))

    def test_parallel_distinct_sessions_cannot_oversell_main_prize(self):
        self.sql('UPDATE campaign_control SET spins_total=100;')
        with ThreadPoolExecutor(max_workers=8) as pool:
            outputs=list(pool.map(lambda i:self.issue(
                f'00000000-0000-4000-8000-{i:012d}',prefix='SELECT audit.seed_for(0,.001);').stdout.strip(),range(1,17)))
        self.assertEqual(sum(row.startswith('ensaio|') for row in outputs),1)
        self.assertEqual(sum(row.startswith('5|') for row in outputs),15)
        self.assertEqual(self.sql('SELECT count(*),count(DISTINCT coupon_code) FROM campaign_awards;').stdout.strip(),'16|16')
        self.assertEqual(self.sql('SELECT sum(claimed) FROM campaign_prizes;').stdout.strip(),'16')

    def test_anon_and_authenticated_cannot_issue_or_read_awards(self):
        self.issue()
        for role in ('anon','authenticated'):
            with self.subTest(role=role):
                result=self.sql(f"SET ROLE {role}; SELECT * FROM issue_campaign_award('{SESSION}','direto');",ok=False)
                self.assertNotEqual(result.returncode,0)
                self.assertIn('permission denied',result.stderr)
                result=self.sql(f'SET ROLE {role}; SELECT * FROM campaign_awards;',ok=False)
                self.assertTrue(result.returncode!=0 or result.stdout.strip()=='')
        self.assertTrue(self.issue('00000000-0000-4000-8000-000000000002',prefix='SET ROLE service_role;').stdout.strip().startswith('5|'))

    def test_null_session_and_duplicate_code_rejected_atomically(self):
        result=self.sql("SELECT * FROM issue_campaign_award(NULL,'direto');",ok=False)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(self.sql('SELECT spins_total FROM campaign_control;').stdout.strip(),'0')
        self.issue()
        result=self.sql("""INSERT INTO campaign_awards(session_id,prize_id,coupon_code,expires_at)
          SELECT '00000000-0000-4000-8000-000000000002',prize_id,coupon_code,expires_at FROM campaign_awards;""",ok=False)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('duplicate key',result.stderr)
        self.assertEqual(self.sql('SELECT count(*) FROM campaign_awards;').stdout.strip(),'1')

    def test_unknown_source_is_normalized_without_breaking_the_award(self):
        self.issue(source='origem-inexistente')
        self.assertEqual(self.sql('SELECT source_id FROM campaign_awards;').stdout.strip(),'direto')


if __name__=='__main__':
    unittest.main(verbosity=2)
