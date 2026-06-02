' run-hidden.vbs
' MicroBubble Local Ops - Hidden PowerShell Launcher
'
' Usage: wscript.exe "X:\path\run-hidden.vbs" "X:\path\some-script.ps1" [args...]
'
' Purpose: launch a PowerShell script with NO visible window.
' Used by schtasks (Task Scheduler) to avoid the popup that flashes
' every 5 minutes when the user-identity session runs PowerShell directly.
'
' Why VBScript:
'   - schtasks starting powershell.exe directly shows a console window
'     (interactive session, current-user identity).
'   - powershell.exe -WindowStyle Hidden still spawns a hidden window but
'     a brief console may flash in some Windows builds.
'   - VBScript via wscript.exe runs in a hidden host by default; calling
'     WshShell.Run with intWindowStyle=0 (HIDE) starts the child process
'     fully hidden, no flash, no taskbar entry.
'
' Compatibility: Windows 7+ (uses WScript.Shell Run method).
' Requires: PowerShell on PATH (default: %SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe).

Option Explicit

Dim shell, fso, scriptPath, psExe, cmd

If WScript.Arguments.Count < 1 Then
    WScript.Echo "Usage: run-hidden.vbs <path-to-ps1> [args...]"
    WScript.Quit 1
End If

scriptPath = WScript.Arguments(0)
If Not CreateObject("Scripting.FileSystemObject").FileExists(scriptPath) Then
    ' Log to Application event log; non-fatal
    WScript.Echo "Script not found: " & scriptPath
    WScript.Quit 2
End If

' Build powershell command line, preserving any extra args
psExe = "powershell.exe"
cmd = """" & psExe & """ -NoProfile -ExecutionPolicy Bypass -File """ & scriptPath & """"
Dim i
For i = 1 To WScript.Arguments.Count - 1
    cmd = cmd & " """ & WScript.Arguments(i) & """"
Next

Set shell = CreateObject("Wscript.Shell")
' intWindowStyle: 0 = HIDE, bWaitOnReturn: False = don't block wscript
shell.Run cmd, 0, False
Set shell = Nothing

WScript.Quit 0
