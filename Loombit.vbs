' Loombit.vbs — lanza Loombit Operator SIN ninguna ventana de consola.
' Es el destino del acceso directo del escritorio. Llama a scripts\start_loombit.ps1
' con la ventana oculta (modo 0), de modo que ni siquiera parpadea una consola.

Dim fso, shell, here, ps1, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
here = fso.GetParentFolderName(WScript.ScriptFullName)
ps1 = here & "\scripts\start_loombit.ps1"
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & ps1 & """"
shell.Run cmd, 0, False
