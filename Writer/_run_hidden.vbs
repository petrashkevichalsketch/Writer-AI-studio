Set WshShell = CreateObject("WScript.Shell")
' 0 = скрытое окно, False = не ждать завершения
WshShell.Run "cmd /c """ & WshShell.CurrentDirectory & "\_run.bat""", 0, False