"""Start a disposable localhost Kafka broker and run real Kafka/PostgreSQL tests."""

import argparse
import base64
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java', type=Path, required=True)
    parser.add_argument('--kafka-dir', type=Path, required=True)
    parser.add_argument('--postgres-bin', type=Path, required=True)
    args = parser.parse_args()
    root = ROOT / '.local'
    root.mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='kafka-validation-', dir=root))
    with socket.socket() as a, socket.socket() as b:
        a.bind(('127.0.0.1', 0))
        b.bind(('127.0.0.1', 0))
        port, controller_port = a.getsockname()[1], b.getsockname()[1]
    properties = directory / 'server.properties'
    properties.write_text('\n'.join([
        'process.roles=broker,controller', 'node.id=1',
        f'listeners=PLAINTEXT://127.0.0.1:{port},CONTROLLER://127.0.0.1:{controller_port}',
        f'advertised.listeners=PLAINTEXT://127.0.0.1:{port}',
        'listener.security.protocol.map=PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT',
        'controller.listener.names=CONTROLLER', 'inter.broker.listener.name=PLAINTEXT',
        f'controller.quorum.bootstrap.servers=127.0.0.1:{controller_port}',
        f'log.dirs={(directory / "data").as_posix()}',
        'offsets.topic.replication.factor=1', 'transaction.state.log.replication.factor=1',
        'transaction.state.log.min.isr=1', 'group.initial.rebalance.delay.ms=0',
        'auto.create.topics.enable=false', 'num.partitions=3',
    ]) + '\n', encoding='utf-8')
    command = [str(args.java.resolve()), '-Xmx512m', '-cp', str(args.kafka_dir.resolve() / 'libs/*')]
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    cluster_id = base64.urlsafe_b64encode(uuid4().bytes).decode().rstrip('=')
    with (directory / 'format.log').open('w') as output:
        subprocess.run([*command, 'kafka.tools.StorageTool', 'format', '--standalone', '-t', cluster_id,
                        '-c', str(properties)], check=True, stdout=output, stderr=subprocess.STDOUT, creationflags=flags, timeout=60)
    with (directory / 'broker.log').open('w') as output:
        broker = subprocess.Popen([*command, 'kafka.Kafka', str(properties)], stdout=output,
                                  stderr=subprocess.STDOUT, creationflags=flags)
        try:
            deadline = time.monotonic() + 60
            while True:
                if broker.poll() is not None:
                    raise RuntimeError(f'Kafka exited; see {directory / "broker.log"}')
                try:
                    with socket.create_connection(('127.0.0.1', port), timeout=1):
                        break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Kafka did not start within 60 seconds')
                    time.sleep(0.5)
            subprocess.run([sys.executable, str(ROOT / 'scripts/verify_postgres.py'), '--bin-dir',
                str(args.postgres_bin.resolve()), '--kafka-bootstrap', f'127.0.0.1:{port}'], check=True, cwd=ROOT)
            print('Real Kafka/PostgreSQL replay and offset checks passed.', flush=True)
        finally:
            broker.terminate()
            try:
                broker.wait(timeout=20)
            except subprocess.TimeoutExpired:
                broker.kill()
                broker.wait(timeout=10)
            print('Disposable Kafka broker stopped.', flush=True)


if __name__ == '__main__':
    main()
