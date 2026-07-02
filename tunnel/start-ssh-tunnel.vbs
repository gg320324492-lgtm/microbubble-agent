Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File E:\microbubble-agent\frp\start-ssh-tunnel.ps1", 0, False
