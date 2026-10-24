"""Reproduce the isolated cross-repository checks. Never uses remote DB credentials."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import runpy
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
IMAGE='postgres:17@sha256:b8faeff7712663c2773a190181e1246e37e364b887611c04658c28b44e2408fe'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--master',type=Path,default=ROOT.parent/'bel-m-masterpiece')
    parser.add_argument('--site',type=Path,default=ROOT.parent/'bel-m-experience-site')
    parser.add_argument('--bun',default=shutil.which('bun'))
    parser.add_argument('--output',type=Path,default=Path('/tmp/belem-stack-results'))
    args=parser.parse_args()
    if not args.bun:parser.error('Install Bun and put it on PATH, or pass --bun')
    args.master=args.master.resolve()
    args.site=args.site.resolve()
    args.output=args.output.resolve()
    for repo in (args.master,args.site):
        if not (repo/'node_modules').is_dir():parser.error(f'Run bun install --frozen-lockfile in {repo}')
    for port in (55432,55433,8081):
        with socket.socket() as sock:
            if sock.connect_ex(('127.0.0.1',port))==0:parser.error(f'Port {port} already in use; no process was stopped')
    args.output.mkdir(parents=True,exist_ok=True)
    container='belem-stack-'+uuid.uuid4().hex[:12]
    processes=[];files=[];commands=[]
    env=dict(os.environ)
    for name in list(env):
        if any(word in name.upper() for word in ('SUPABASE','ASAAS','MERCADOPAGO','ROLETA','BELEM_')):env.pop(name)
    env.update(BELEM_SUPABASE_URL='http://127.0.0.1:55433',BELEM_SUPABASE_PUBLISHABLE_KEY='sb_publishable_isolated')
    native_run=subprocess.run
    def execute(command,cwd,label,extra_env=None):
        print('Running',label,flush=True)
        with (args.output/(label+'.log')).open('w') as log:
            native_run(command,cwd=cwd,env={**env,**(extra_env or {})},stdout=log,stderr=subprocess.STDOUT,check=True)
        commands.append(label)
    def start(command,cwd,label):
        log=(args.output/(label+'.log')).open('w');files.append(log)
        proc=subprocess.Popen(command,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        processes.append(proc);return proc
    def ready(url,proc):
        for _ in range(180):
            if proc.poll() is not None:raise RuntimeError('Test service exited; inspect logs')
            try:
                with urllib.request.urlopen(url,timeout=1) as response:
                    if response.status==200:return
            except Exception:pass
            time.sleep(.25)
        raise RuntimeError('Test service did not become ready')
    try:
        native_run(['docker','run','--detach','--name',container,'--publish','127.0.0.1:55432:55432',
            '--tmpfs','/var/lib/postgresql/data','-e','POSTGRES_USER=fixture_admin',
            '-e','POSTGRES_HOST_AUTH_METHOD=trust',IMAGE,'-c','port=55432'],check=True,capture_output=True)
        for _ in range(150):
            p=native_run(['docker','exec',container,'cat','/proc/1/comm'],capture_output=True,text=True)
            q=native_run(['docker','exec',container,'pg_isready','-p','55432','-U','fixture_admin'],capture_output=True)
            if p.stdout.strip()=='postgres' and q.returncode==0:break
            time.sleep(.2)
        else:raise RuntimeError('Disposable database did not initialize')
        Path('/tmp/roleta-db').mkdir(exist_ok=True)
        def psql_adapter(command,*a,**kw):
            # Adapt only the psql transport of the original fixture bootstrap.
            if isinstance(command,list) and command[0]=='psql':
                copied=command[1:];i=copied.index('-f');sql=Path(copied[i+1]).read_text();del copied[i:i+2]
                result=native_run(['docker','exec','-i',container,'psql',*copied],input=sql,**kw)
                if result.returncode:raise RuntimeError('Fixture bootstrap failed: '+result.stderr[-2000:])
                return result
            return native_run(command,*a,**kw)
        with patch('subprocess.run',psql_adapter):
            runpy.run_path(str(args.master/'scripts/roleta-local-bootstrap.py'),run_name='__isolated_fixture__')
        native_run(['docker','exec','-i',container,'psql','-X','-p','55432','-U','fixture_admin','-d','postgres',
            '-v','ON_ERROR_STOP=1'],input='CREATE TABLE public.isolated_test_marker(value boolean NOT NULL); INSERT INTO public.isolated_test_marker VALUES(true);',text=True,check=True,capture_output=True)
        execute([args.bun,'scripts/roleta-isolated-tests.mjs'],args.master,'master-sql')
        config=args.output/'vitest.master.config.mts'
        config.write_text('export default '+json.dumps({'resolve':{'alias':{'@':str(args.master/'src')}},'test':{
            'include':['src/lib/roleta.test.ts','src/lib/roleta-endpoint.integration.test.ts'],'testTimeout':20000}})+';\n')
        execute([args.bun,'x','vitest','run','--config',str(config)],args.master,'master-endpoint',{'ISOLATED_ROLETA_TEST':'1'})
        execute([args.bun,'x','vitest','run','--config','vitest.checkout.config.ts'],args.site,'checkout-regressions')
        transport=start([args.bun,str(ROOT/'tests/integration/serve-isolated.ts'),str(args.master)],args.master,'transport')
        ready('http://127.0.0.1:55433/health',transport)
        site=start([args.bun,'x','vite','--host','127.0.0.1','--port','8081','--strictPort'],args.site,'site')
        ready('http://127.0.0.1:8081/',site)
        execute([sys.executable,str(ROOT/'tests/integration/full_stack_browser.py')],ROOT,'browser-full-stack')
        (args.output/'result.json').write_text(json.dumps({'status':'passed','groups':commands,
            'master':native_run(['git','rev-parse','HEAD'],cwd=args.master,capture_output=True,text=True,check=True).stdout.strip(),
            'site':native_run(['git','rev-parse','HEAD'],cwd=args.site,capture_output=True,text=True,check=True).stdout.strip()},indent=2)+'\n')
        print('All integration checks passed; temporary services will be removed.',flush=True)
    finally:
        for proc in reversed(processes):
            if proc.poll() is None:
                os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=8)
                except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
        for log in files:log.close()
        native_run(['docker','rm','-f',container],capture_output=True)

if __name__=='__main__':main()
