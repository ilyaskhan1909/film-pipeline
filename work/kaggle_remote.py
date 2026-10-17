"""Official Kaggle MCP transport. Local token only; no credentials in logs."""
import argparse, json, sys
from pathlib import Path
import requests

TOKEN_PATH=Path('C:/Users/ilyas/.kaggle/access_token')
ENDPOINT='https://www.kaggle.com/mcp'

def decode(response):
    response.raise_for_status()
    if 'text/event-stream' in response.headers.get('Content-Type',''):
        for block in response.text.split('\n\n'):
            data='\n'.join(line[5:].lstrip() for line in block.splitlines() if line.startswith('data:'))
            if data:
                try: return json.loads(data)
                except json.JSONDecodeError: pass
        raise ValueError('No JSON-RPC response')
    return response.json()

class KaggleRemote:
    def __init__(self):
        token=TOKEN_PATH.read_text(encoding='utf-8-sig').strip()
        if not token: raise ValueError('Local token file is empty')
        self.session=requests.Session()
        self.session.headers.update({'Authorization':'Bearer '+token,'Content-Type':'application/json',
                                    'Accept':'application/json, text/event-stream'})
        self.counter=0
        response=self.session.post(ENDPOINT,json={'jsonrpc':'2.0','id':0,'method':'initialize',
            'params':{'protocolVersion':'2025-06-18','capabilities':{},
                      'clientInfo':{'name':'codex-kaggle-notebook-work','version':'1.0'}}},timeout=(10,40))
        payload=decode(response)
        if 'error' in payload: raise ValueError('MCP initialization failed')
        self.session.headers['MCP-Protocol-Version']=payload['result']['protocolVersion']
        if response.headers.get('Mcp-Session-Id'): self.session.headers['Mcp-Session-Id']=response.headers['Mcp-Session-Id']
        self.session.post(ENDPOINT,json={'jsonrpc':'2.0','method':'notifications/initialized'},timeout=(10,40)).raise_for_status()

    def rpc(self,method,params):
        self.counter+=1
        payload=decode(self.session.post(ENDPOINT,json={'jsonrpc':'2.0','id':self.counter,'method':method,'params':params},timeout=(10,55)))
        if 'error' in payload:
            return {'rpc_error':payload['error']}
        return payload['result']

    def call(self,name,arguments): return self.rpc('tools/call',{'name':name,'arguments':arguments})

def unpack(result):
    if 'structuredContent' in result: return result['structuredContent']
    content=result.get('content',[])
    strings=[c.get('text','') for c in content if c.get('type')=='text']
    if len(strings)==1:
        try: return json.loads(strings[0])
        except json.JSONDecodeError: return strings[0]
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['schemas','call'])
    parser.add_argument('tool',nargs='?')
    parser.add_argument('--arguments',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--quiet',action='store_true')
    args=parser.parse_args()
    remote=KaggleRemote()
    if args.command=='schemas':
        data=remote.rpc('tools/list',{})
        result=[t for t in data.get('tools',[]) if any(w in t['name'] for w in ('notebook','quota','session','python'))]
    else:
        if not args.tool or not args.arguments: raise ValueError('Tool name and arguments file required')
        result=remote.call(args.tool,json.loads(args.arguments.read_text(encoding='utf-8')))
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    if args.quiet:
        print(json.dumps({'tool':args.tool,'saved':str(args.output),'is_error':bool(result.get('isError') or result.get('rpc_error')) if isinstance(result,dict) else False}))
    else:
        print(json.dumps(unpack(result) if isinstance(result,dict) else result,ensure_ascii=False,indent=2))
    if isinstance(result,dict) and (result.get('isError') or result.get('rpc_error')): sys.exit(1)

if __name__=='__main__':
    try: main()
    except requests.RequestException as exc:
        print(json.dumps({'transport_error':type(exc).__name__,'http_status':getattr(getattr(exc,'response',None),'status_code',None)})); sys.exit(2)
    except Exception as exc:
        print(json.dumps({'error_type':type(exc).__name__})); sys.exit(3)
