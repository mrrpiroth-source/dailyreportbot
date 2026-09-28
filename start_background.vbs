' VBScript to run KHQR Bot invisibly in the background on Windows
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.Run Chr(34) & WshShell.CurrentDirectory & "\.venv\Scripts\python.exe" & Chr(34) & " main.py", 0, False
Set WshShell = Nothing
