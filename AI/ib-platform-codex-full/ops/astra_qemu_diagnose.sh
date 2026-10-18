#!/usr/bin/env bash
# READ ONLY: run manually on Astra Linux SE 1.7.6 host, not from Ubuntu VM.
# Output may contain environment metadata: review before sharing externally.
set -u
printf '\n=== OS / KERNEL ===\n'
cat /etc/os-release 2>/dev/null || true
uname -r
printf '\n=== CPU (brief) ===\n'
lscpu 2>/dev/null | grep -E 'Architecture:|Model name:|CPU\(s\):|Socket\(s\):|Virtualization:|Flags:' | cut -c1-240 || true
printf '\n=== QEMU ===\n'
if command -v qemu-system-x86_64 >/dev/null; then
  qemu-system-x86_64 --version | head -3
  echo '=== Supported machine types ==='
  qemu-system-x86_64 -machine help | head -80
else
  echo 'qemu-system-x86_64 not found'
fi
printf '\n=== LIBVIRT VERSIONS ===\n'
if command -v virsh >/dev/null; then
  virsh -c qemu:///system version 2>&1 || echo 'virsh requires authorized access'
else
  echo 'virsh not found'
fi
printf '\n=== KVM DEVICE ===\n'
ls -l /dev/kvm 2>&1 || true
printf '\n=== PACKAGES ===\n'
dpkg-query -W -f='${Package} ${Version}\n' 'qemu*' 'libvirt*' 'astra-kvm' 2>/dev/null | head -80 || true
printf '\n=== END. Manually review/redact before giving output to Codex. ===\n'
