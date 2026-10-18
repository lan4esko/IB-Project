# Read-only Windows Server 2019 network / VirtualBox inventory.
# IMPORTANT: output may contain private addresses: keep in approved local storage, never git add.
# Run as an authorized administrator in PowerShell; never prints password / API keys.
$ErrorActionPreference = 'Continue'
Write-Output '=== OS ==='
Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, OsBuildNumber | Format-List
Write-Output '=== Adapters ==='
Get-NetAdapter | Select-Object Name, InterfaceDescription, Status, LinkSpeed | Format-Table
Write-Output '=== IPv4 ==='
Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceAlias,IPAddress,PrefixLength | Format-Table
Write-Output '=== Routes ==='
Get-NetRoute -AddressFamily IPv4 | Select-Object DestinationPrefix,NextHop,InterfaceAlias | Format-Table
Write-Output '=== Hyper-V feature ==='
Get-WindowsFeature -Name Hyper-V -ErrorAction SilentlyContinue | Select-Object Name,InstallState
Write-Output '=== Ports 80 443 8443 10443 ==='
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
 Where-Object { $_.LocalPort -in @(80,443,8443,10443) } |
 Select-Object LocalAddress,LocalPort,OwningProcess | Format-Table
$VBox='C:\Program Files\Oracle\VirtualBox\VBoxManage.exe'
if (Test-Path $VBox) {
  Write-Output '=== VirtualBox version ==='
  & $VBox --version
  Write-Output '=== Registered VMs ==='
  & $VBox list vms
  Write-Output '=== Running VMs ==='
  & $VBox list runningvms
} else { Write-Warning 'VBoxManage not found in default path; check installation and per-user VM registry' }
