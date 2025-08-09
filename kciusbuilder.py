import os
import shutil
import zipfile
import subprocess
import re
import random
import string
import signal
import time
from colorama import Fore, Style
import sys

def limpiar_pantalla():
    if os.name == 'posix':
        os.system('clear')
    elif os.name == 'nt':
        os.system('cls')

limpiar_pantalla()

CRE = Fore.RED
CYE = Fore.YELLOW
CGR = Fore.GREEN
CBL = Fore.BLUE
CBLE = Fore.CYAN
CBK = Fore.WHITE
CGY = Fore.LIGHTBLACK_EX
BLD = Style.BRIGHT
CNC = Style.RESET_ALL

banner = f"""
{BLD}{CRE}    _____          _____           _____    
{BLD}{CRE} __| __  |__   ___|    _|__     __|_    |__ 
{BLD}{CBL}|  |/ /     | |    \  /  | |   |    |      |
{BLD}{CBL}|     \     | |     \/   | |  _|    |      |
{BLD}{CBL}|__|\__\  __| |__/\__/|__|_| |______|    __|
{BLD}{CBL}   |_____|        |_____|         |_____|   
{BLD}{CYE}  KMJ | Ciberseguridad | https://kmj.cl 
{CNC}"""

print(banner)
#by Kcius

def get_user_input():
    container_name = input(" Nombre del NUEVO contenedor: ").strip()

    print("\n Vulnerabilidades disponibles:")
    available = [d for d in os.listdir('templates') if os.path.isdir(os.path.join('templates', d))]
    for i, vuln in enumerate(available, 1):
        print(f"{i}. {vuln}")

    selected = input("\n Ingresa los números de las vulnerabilidades separadas por coma (ej: 1,3,4): ").strip()
    selected_indices = [int(i)-1 for i in selected.split(',') if i.strip().isdigit()]
    selected_vulns = [available[i] for i in selected_indices if 0 <= i < len(available)]

    return container_name, selected_vulns

def extract_exposed_ports(vuln_path):
    ports_conf = os.path.join(vuln_path, 'ports.conf')
    ports = []

    if os.path.exists(ports_conf):
        with open(ports_conf, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '-' in line:
                        try:
                            start, end = map(int, line.split('-'))
                            ports.extend(map(str, range(start, end+1)))
                        except Exception:
                            pass
                    else:
                        ports.append(line)
    return list(set(ports))

def generate_protect_sh(output_dir):
    protect_sh_path = os.path.join(output_dir, 'protect.sh')

    flag_random = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    flag_message = f"GRANDE REY - FLAG: {flag_random}"

    content = f"""#!/bin/bash
sleep 5

# Crear flag en /root
FLAG_PATH="/root/.super_flag"
echo "{flag_message}" > "$FLAG_PATH"
chmod 600 "$FLAG_PATH"
chown root:root "$FLAG_PATH"

while true; do
    # Buscar procesos docker exec y matar solo si es root
    for pid in $(pgrep -f "docker-exec"); do
        user=$(ps -o user= -p $pid 2>/dev/null)
        if [ "$user" = "root" ]; then
            echo "$(date '+%F %T') - Bloqueado intento docker exec de root" >> /var/log/protect.log
            kill -9 $pid 2>/dev/null
        fi
    done

    # Ajustar permisos críticos
    chmod 750 /bin/bash /bin/sh 2>/dev/null
    chmod 000 /bin/su /usr/bin/sudo 2>/dev/null
    sleep 5
done
"""
    with open(protect_sh_path, 'w') as f:
        f.write(content)

    os.chmod(protect_sh_path, 0o755)
    print(f" protect.sh generado en: {protect_sh_path}")

def generate_dockerfile(container_name, selected_vulns):
    output_dir = f'output/{container_name}'
    os.makedirs(output_dir, exist_ok=True)

    dockerfile_path = os.path.join(output_dir, 'Dockerfile')
    with open(dockerfile_path, 'w') as out:
        out.write(f"FROM ubuntu\n")
        out.write("ENV DEBIAN_FRONTEND=noninteractive\n")
        out.write("RUN apt-get update && apt-get install -y sudo curl wget net-tools procps && rm -rf /var/lib/apt/lists/*\n\n")

        for vuln in selected_vulns:
            vuln_path = os.path.join('templates', vuln)
            
            renamed_files = {}
            for filename in os.listdir(vuln_path):
                if filename not in ['start_snippet.sh', 'ports.conf', 'Dockerfile', 'fragment_Dockerfile']:
                    src = os.path.join(vuln_path, filename)
                    dst_name = f"{vuln}_{filename}"
                    dst = os.path.join(output_dir, dst_name)
                    if os.path.isfile(src):
                        shutil.copy(src, dst)
                        renamed_files[filename] = dst_name

            frag_path = os.path.join(vuln_path, 'fragment_Dockerfile')
            if os.path.isfile(frag_path):
                with open(frag_path, 'r') as frag:
                    content = frag.read()

                    def replace_copy_add(match):
                        instr = match.group(1)
                        src_file = match.group(2)
                        dst_path = match.group(3)
                        new_src = renamed_files.get(os.path.basename(src_file), src_file)
                        return f"{instr} {new_src} {dst_path}"

                    content = re.sub(
                        r'^(COPY|ADD)\s+(\S+)\s+(\S+)',
                        replace_copy_add,
                        content,
                        flags=re.MULTILINE
                    )

                    out.write(f"# --- {vuln} ---\n")
                    out.write(content + "\n")

        out.write("\nCOPY start.sh /start.sh\n")
        out.write("RUN chmod +x /start.sh\n")
        out.write("COPY protect.sh /protect.sh\n")
        out.write("RUN chmod +x /protect.sh\n")
        out.write('CMD ["/bin/bash", "-c", "/start.sh & /protect.sh"]\n')

    print(f" Dockerfile generado en: {dockerfile_path}")
    return output_dir

def generate_start_sh(container_name, selected_vulns, output_dir):
    foreground_priority = ['http_xss', 'web_sqli', 'tomcat_default']
    fg_selected = [v for v in foreground_priority if v in selected_vulns]
    fg_main = fg_selected[0] if fg_selected else None

    start_sh_path = os.path.join(output_dir, 'start.sh')
    commands = ["#!/bin/bash\n", "echo 'Iniciando servicios...'\n"]

    for vuln in selected_vulns:
        snippet_path = os.path.join('templates', vuln, 'start_snippet.sh')
        if os.path.isfile(snippet_path):
            with open(snippet_path, 'r') as f:
                snippet_content = f.read().strip()

                commands.append(f"echo '--- Iniciando {vuln} ---'")

                if vuln == fg_main:
                    commands.append(snippet_content)
                else:
                    if snippet_content.endswith('&'):
                        commands.append(snippet_content)
                    else:
                        commands.append(snippet_content + " &")

                commands.append("")

    commands.append("echo 'Todos los servicios iniciados. Manteniendo contenedor activo...'")
    commands.append("tail -f /dev/null")

    with open(start_sh_path, 'w') as f:
        f.write("\n".join(commands) + "\n")

    os.chmod(start_sh_path, 0o755)
    print(f" start.sh generado en: {start_sh_path}")

def build_and_package(container_name, output_dir, selected_vulns):
    print("\n Construyendo imagen Docker...")
    image_tag = container_name.lower()

    all_ports = []
    for vuln in selected_vulns:
        vuln_path = os.path.join('templates', vuln)
        all_ports.extend(extract_exposed_ports(vuln_path))
    ports = list(set(all_ports))

    try:
        subprocess.run(["docker", "build", "-t", image_tag, "."], cwd=output_dir, check=True)
    except subprocess.CalledProcessError as e:
        print(f" Error al construir la imagen Docker: {e}")
        return

    tar_path = os.path.join(output_dir, f"{container_name}.tar")
    subprocess.run(["docker", "save", "-o", tar_path, image_tag], check=True)
    print(f" Imagen guardada en {tar_path}")

    run_sh_path = os.path.join(output_dir, "run.sh")
    with open(run_sh_path, 'w') as run_sh:
        run_sh.write(f"""#!/bin/bash

docker load -i {container_name}.tar

CONTAINER_NAME="{container_name.lower()}"

if [ "$(docker ps -aq -f name=$CONTAINER_NAME)" ]; then
    echo "⚠ Contenedor existente detectado, deteniendo y eliminando..."
    docker stop $CONTAINER_NAME >/dev/null 2>&1 || true
    docker rm $CONTAINER_NAME >/dev/null 2>&1 || true
fi

PORT_ARGS=""
""")
        for port in ports:
            run_sh.write(f'PORT_ARGS="$PORT_ARGS -p {port}:{port}"\n')

        run_sh.write(f"""
CID=$(docker run -d $PORT_ARGS --name $CONTAINER_NAME {image_tag})

IP=$(docker inspect -f '{{{{range .NetworkSettings.Networks}}}}{{{{.IPAddress}}}}{{{{end}}}}' $CID)
echo " Máquina desplegada"
echo " IP interna: $IP"
echo " Presiona Ctrl+C para detener y destruir el contenedor..."

trap_ctrl_c() {{
    echo ' Deteniendo contenedor...'
    docker stop $CID
    exit 0
}}

trap trap_ctrl_c INT

while true; do sleep 1; done
""")
    os.chmod(run_sh_path, 0o755)

    zip_path = f"{container_name}.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(os.path.join(output_dir, f"{container_name}.tar"), arcname=f"{container_name}.tar")
        zipf.write(run_sh_path, arcname="run.sh")

    print(f"\n Archivo final empaquetado: {zip_path}")

def main():
    container_name, selected_vulns = get_user_input()
    output_dir = generate_dockerfile(container_name, selected_vulns)
    generate_start_sh(container_name, selected_vulns, output_dir)
    generate_protect_sh(output_dir)
    build_and_package(container_name, output_dir, selected_vulns)

if __name__ == "__main__":
    def handle_ctrl_c(signum, frame):
        print("\nSaliendo...bye bye")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_ctrl_c)

    try:
        main()
    except Exception as e:
        print(f"\n[Error] {e}")
        sys.exit(1)
