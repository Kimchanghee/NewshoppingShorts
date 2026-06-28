Option Explicit

Dim shell, fso, scriptDir, cmdPath, command, exitCode, i
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
cmdPath = fso.BuildPath(scriptDir, "run_summer_coupang_queue_once.cmd")
command = """" & cmdPath & """"

For i = 0 To WScript.Arguments.Count - 1
    command = command & " " & QuoteArg(WScript.Arguments(i))
Next

exitCode = shell.Run(command, 0, True)
WScript.Quit exitCode

Function QuoteArg(value)
    QuoteArg = """" & Replace(CStr(value), """", """""") & """"
End Function
