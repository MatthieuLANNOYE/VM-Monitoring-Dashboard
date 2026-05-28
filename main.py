from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict
from dotenv import load_dotenv
from collections import defaultdict, deque
import paramiko
import os
import time

load_dotenv()

app = FastAPI(title="VM Monitor API", version="1.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Stocker l'historique des métriques (max 60 points par VM)
metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=60))

class DiskUsage(BaseModel):
    path: str
    size_gb: float

class VMMetric(BaseModel):
    name: str
    host: str
    status: str
    cpu: float
    ram: float
    disk: float
    uptime: str
    net_kbps: float
    checked_at: int
    error: Optional[str] = None

SSH_USERNAME = os.getenv("SSH_USERNAME", "")
SSH_PASSWORD = os.getenv("SSH_PASSWORD", "")
SSH_PORT = int(os.getenv("SSH_PORT", "22"))

VMS = []
for i in range(1, 21):
    name = os.getenv(f"VM{i}_NAME")
    host = os.getenv(f"VM{i}_HOST")
    if host:
        VMS.append({
            "name": name or f"vm-{i}",
            "host": host,
            "user": os.getenv(f"VM{i}_USER") or SSH_USERNAME,
            "pass": os.getenv(f"VM{i}_PASS") or SSH_PASSWORD,
        })

REMOTE_SCRIPT = """
CPU=$(awk '/^cpu /{t=$2+$3+$4+$5+$6+$7+$8; idle=$5; print (t-idle)/t*100}' /proc/stat)
RAM=$(free | awk '/Mem:/{print $3/$2*100}')
DISK=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
UPTIME=$(uptime | sed 's/.*up //' | sed 's/[,].*//' | xargs)
echo CPU=$CPU
echo RAM=$RAM
echo DISK=$DISK
echo UPTIME=$UPTIME
"""

DISK_ANALYSIS_SCRIPT = """
echo "TOP_DIRS_START"
du -shx --exclude=/proc --exclude=/sys --exclude=/dev --exclude=/run /* 2>/dev/null | sort -rh | head -5 | while read size path; do
    echo "$path|$size"
done
echo "TOP_DIRS_END"
"""

def parse_output(raw: str):
    data = {}
    for line in raw.splitlines():
        if '=' in line:
            k, v = line.split('=', 1)
            data[k.strip()] = v.strip()
    return data

def parse_disk_usage(raw: str) -> List[DiskUsage]:
    """Parse la sortie du script d'analyse disque"""
    top_dirs = []
    in_section = False
    
    print(f"DEBUG - Raw output:\n{raw}")
    
    for line in raw.splitlines():
        line = line.strip()
        if line == "TOP_DIRS_START":
            in_section = True
            continue
        if line == "TOP_DIRS_END":
            break
        if in_section and '|' in line:
            try:
                parts = line.split('|')
                if len(parts) != 2:
                    print(f"DEBUG - Invalid line format: {line}")
                    continue
                    
                path = parts[0].strip()
                size_str = parts[1].strip()
                
                print(f"DEBUG - Parsing: path={path}, size={size_str}")
                
                # Conversion de la taille
                if size_str.endswith('G'):
                    size_gb = float(size_str[:-1])
                elif size_str.endswith('M'):
                    size_gb = round(float(size_str[:-1]) / 1024, 2)
                elif size_str.endswith('K'):
                    size_gb = round(float(size_str[:-1]) / (1024 * 1024), 2)
                elif size_str.endswith('T'):
                    size_gb = float(size_str[:-1]) * 1024
                else:
                    size_gb = round(float(size_str) / (1024 * 1024 * 1024), 2)
                
                top_dirs.append(DiskUsage(
                    path=path,
                    size_gb=size_gb
                ))
                print(f"DEBUG - Added: {path} = {size_gb} GB")
            except Exception as e:
                print(f"DEBUG - Error parsing line '{line}': {e}")
                continue
    
    print(f"DEBUG - Total dirs found: {len(top_dirs)}")
    return top_dirs

def collect_metrics(vm) -> VMMetric:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=vm['host'],
            port=SSH_PORT,
            username=vm['user'],
            password=vm['pass'],
            look_for_keys=False,
            allow_agent=False,
            timeout=8,
        )
        stdin, stdout, stderr = client.exec_command("bash -s", timeout=12)
        stdin.write(REMOTE_SCRIPT)
        stdin.channel.shutdown_write()
        output = stdout.read().decode()
        err = stderr.read().decode().strip()
        if not output and err:
            raise RuntimeError(err)
        parsed = parse_output(output)
        
        timestamp = int(time.time())
        cpu_val = round(float(parsed.get('CPU', 0)), 1)
        ram_val = round(float(parsed.get('RAM', 0)), 1)
        
        # Ajouter à l'historique
        metrics_history[vm['host']].append({
            'timestamp': timestamp,
            'cpu': cpu_val,
            'ram': ram_val
        })
        
        return VMMetric(
            name=vm['name'],
            host=vm['host'],
            status='up',
            cpu=cpu_val,
            ram=ram_val,
            disk=float(parsed.get('DISK', 0)),
            uptime=parsed.get('UPTIME', 'unknown'),
            net_kbps=0.0,
            checked_at=timestamp,
        )
    except Exception as e:
        return VMMetric(
            name=vm['name'],
            host=vm['host'],
            status='down',
            cpu=0, ram=0, disk=0,
            uptime='unreachable',
            net_kbps=0,
            checked_at=int(time.time()),
            error=str(e),
        )
    finally:
        client.close()

def get_disk_details(vm) -> List[DiskUsage]:
    """Récupérer les détails d'utilisation disque pour une VM"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print(f"DEBUG - Connecting to {vm['host']} for disk analysis...")
        client.connect(
            hostname=vm['host'],
            port=SSH_PORT,
            username=vm['user'],
            password=vm['pass'],
            look_for_keys=False,
            allow_agent=False,
            timeout=10,
        )
        print(f"DEBUG - Connected, executing disk analysis script...")
        stdin, stdout, stderr = client.exec_command("bash -s", timeout=60)
        stdin.write(DISK_ANALYSIS_SCRIPT)
        stdin.channel.shutdown_write()
        
        output = stdout.read().decode()
        error_output = stderr.read().decode()
        
        print(f"DEBUG - Command output length: {len(output)}")
        print(f"DEBUG - Command errors: {error_output}")
        
        if not output or "TOP_DIRS_START" not in output:
            print("DEBUG - No valid output received")
            return []
            
        return parse_disk_usage(output)
    except Exception as e:
        print(f"DEBUG - Exception in get_disk_details: {e}")
        return []
    finally:
        client.close()

app.mount('/static', StaticFiles(directory='static'), name='static')

@app.get('/')
def dashboard():
    return FileResponse('static/index.html')

@app.get('/health')
def health():
    return {'status': 'ok'}

@app.get('/api/metrics', response_model=List[VMMetric])
def get_metrics():
    if not SSH_USERNAME or not SSH_PASSWORD:
        raise HTTPException(status_code=500, detail='SSH_USERNAME or SSH_PASSWORD missing')
    if not VMS:
        raise HTTPException(status_code=500, detail='No VMs configured in environment')
    return [collect_metrics(vm) for vm in VMS]

@app.get('/api/history/{vm_host}')
def get_history(vm_host: str):
    """Récupérer l'historique des métriques pour une VM"""
    if vm_host not in metrics_history:
        return []
    return list(metrics_history[vm_host])

@app.get('/api/disk/{vm_host}')
def get_disk_analysis(vm_host: str):
    """Récupérer l'analyse détaillée du disque pour une VM"""
    vm = next((v for v in VMS if v['host'] == vm_host), None)
    if not vm:
        raise HTTPException(status_code=404, detail='VM not found')
    
    top_dirs = get_disk_details(vm)
    return {
        'host': vm_host,
        'name': vm['name'],
        'top_dirs': top_dirs
    }