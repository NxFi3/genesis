"""Read-only localhost research viewer. Results stay on this machine."""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlparse,parse_qs


def serve(directory,host='127.0.0.1',port=8769):
    root=Path(directory).resolve()
    if not root.is_dir():raise ValueError('Research results directory does not exist')
    html=(Path(__file__).parent/'data'/'dashboard.html').read_bytes()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def respond(self,status,payload,kind='application/json'):
            self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
        def do_GET(self):
            url=urlparse(self.path)
            if url.path=='/':return self.respond(200,html,'text/html; charset=utf-8')
            if url.path=='/api/index':
                def read(name,default):
                    try:return json.loads((root/name).read_text())
                    except (OSError,ValueError):return default
                return self.respond(200,json.dumps({'trials':read('index.json',[]),'aggregate':read('aggregate.json',{}),'configuration':read('configuration.json',{})}).encode())
            if url.path=='/api/trial':
                identity=parse_qs(url.query).get('id',[''])[0]
                path=(root/identity).resolve()
                if not identity or path.parent!=root or not path.is_dir():return self.respond(400,b'{"error":"Invalid trial ID"}')
                def read(name,default):
                    try:return json.loads((path/name).read_text())
                    except (OSError,ValueError):return default
                events=[];actions=[]
                for name,target in [('events.jsonl',events),('actions.jsonl',actions)]:
                    from collections import deque
                    try:
                        with (path/name).open() as handle:
                            for line in deque(handle,maxlen=2000):
                                try:target.append(json.loads(line))
                                except ValueError:pass
                    except OSError:pass
                metrics=read('metrics.json',[])
                if not metrics:
                    import csv
                    from collections import deque
                    try:
                        with (path/'metrics.csv').open() as handle:
                            for row in deque(csv.DictReader(handle),maxlen=2048):
                                parsed={}
                                for k,v in row.items():
                                    try:parsed[k]=float(v)
                                    except (ValueError,TypeError):parsed[k]=v
                                metrics.append(parsed)
                    except OSError:pass
                payload={'manifest':read('manifest.json',{}),'metrics':metrics,'agents':read('agents.json',[]),'relationships':read('relationships.json',[]),'events':events,'actions':actions,'log_limit':2000}
                return self.respond(200,json.dumps(payload).encode())
            self.respond(404,b'{"error":"Unknown research endpoint"}')
    http=ThreadingHTTPServer((host,port),Handler)
    print(f'Genesis Research Dashboard: http://{host}:{http.server_port}',flush=True)
    try:http.serve_forever()
    finally:http.server_close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory');parser.add_argument('--port',type=int,default=8769)
    args=parser.parse_args()
    try:serve(args.directory,port=args.port)
    except KeyboardInterrupt:pass
if __name__=='__main__':main()
