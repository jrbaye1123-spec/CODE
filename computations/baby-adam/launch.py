#!/usr/bin/env python3
"""Launch Baby Adam E training — writes to log file for real-time monitoring."""
import subprocess, sys
log = open('/home/dsfjliefjsefjsj/Documents/baby_adam_E/train_log.txt', 'w')
proc = subprocess.Popen(
    [sys.executable, '-u', 'train_e.py', '--epochs', '1000', '--batch-size', '8'],
    stdout=log, stderr=subprocess.STDOUT,
    cwd='/home/dsfjliefjsefjsj/Documents/baby_adam_E',
    env={**__import__('os').environ, 'PYTHONUNBUFFERED': '1'},
)
print(f'PID: {proc.pid}')
