' Univention Printer Assignment
' Copyright 2007-2016 Univention GmbH
'
' http://www.univention.de/
'
' All rights reserved.
'
' The source code of this program is made available
' under the terms of the GNU Affero General Public License version 3
' (GNU AGPL V3) as published by the Free Software Foundation.
'
' Binary versions of this program provided by Univention to you as
' well as other copyrighted, protected or trademarked materials like
' Logos, graphics, fonts, specific documentations and configurations,
' cryptographic keys etc. are subject to a license agreement between
' you and Univention and not subject to the GNU AGPL V3.
'
' In the case you use this program under the terms of the GNU AGPL V3,
' the program is provided in the hope that it will be useful,
' but WITHOUT ANY WARRANTY; without even the implied warranty of
' MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
' GNU Affero General Public License for more details.
'
' You should have received a copy of the GNU Affero General Public
' License with the Debian GNU/Linux or Univention distribution in file
' /usr/share/common-licenses/AGPL-3; if not, see
' <http://www.gnu.org/licenses/>.

Dim flagRemoveAllPrinters: flagRemoveAllPrinters = %(flagRemoveAllPrinters)s
Dim showDebug: showDebug = %(flagShowDebug)s
Dim printerList: printerList = "%(printerList)s"
Dim defaultPrinter: defaultPrinter = "%(defaultPrinter)s"
Dim printUIEntryOptions: printUIEntryOptions = "%(printUIEntryOptions)s"

Dim objWshNetwork
Set objWshNetwork = CreateObject("WScript.Network")

if showDebug = 1 Then
    wscript.echo "Starting printer assignment..."
end if

' remove if printers should be deleted before adding new ones
If flagRemoveAllPrinters = 1 Then
    RemoveAllPrinters()
End if

' add printers
if printerList <> "" Then
    items = split(printerList, " ")
    for i = 0 to UBound(items)
        prt = items(i)
        settingsFile = "None"
        if inStr(items(i), ":") then
            prt = split(items(i), ":", 2)(0)
            settingsFile = split(items(i), ":", 2)(1)
        end if

        ' do not apply printer settings if printer already exists
        if printExists(prt) then
            settingsFile = "None"
            if showDebug = 1 Then
                wscript.echo "printer " & prt & " already exists"
            end if
        end if

        ' adding printer
        if showDebug = 1 Then
            wscript.echo "Adding printer " & prt
        end if
        objWshNetwork.AddWindowsPrinterConnection prt

        ' setting preferences from file
        if settingsFile <> "None" then
            if showDebug = 1 Then
                wscript.echo "Apply printer settings from " & settingsFile
            end if
            applyPrinterSettingsFromFile prt, settingsFile
        end if
    next
end if

' setting default printer
if defaultPrinter <> "" Then
    if showDebug = 1 Then
        wscript.echo "Set default printer to " & defaultPrinter
    end if
    objWshNetwork.SetDefaultPrinter defaultPrinter
end if

if showDebug = 1 Then
    wscript.echo "Printer assignment finished."
end if

''''''''
' FINE '
''''''''

' run rundll32 printui.dll,PrintUIEntry
sub applyPrinterSettingsFromFile(printer,file)
    Set objFso = CreateObject("Scripting.FileSystemObject")
    Set objShell = CreateObject("WScript.Shell")
    server = split(split(printer,"\\")(1),"\", 2)(0)
    path = "\\" & server & "\print$\printer-settings\" & file
    cmd = "rundll32 printui.dll,PrintUIEntry"
    cmd = cmd & " /Sr /n" & chr(34) & printer & chr(34) & " /a " & chr(34) & path & chr(34) & " " & printUIEntryOptions
    If (objFso.FileExists(path)) Then
        if showDebug = 1 Then
            wscript.echo "Running " & cmd
        end if
        objShell.Run cmd
    End If
end sub

' check if printer connection exists
function printExists(sPrinter)
    Set objNetwork = WScript.CreateObject("Wscript.Network")
    Set oPrinters = objNetwork.EnumPrinterConnections
    printExists = False
    For j = 0 to oPrinters.Count - 1 Step 2
        if StrComp(sPrinter, oPrinters.Item(j+1)) = 0 then
            printExists = True
            Exit Function
        end if
    Next
end function

' remove all none local printers
sub RemoveAllPrinters()
    dim oPrinters, aPrinter
    Set objNetwork = WScript.CreateObject("Wscript.Network")
    Set oPrinters = objNetwork.EnumPrinterConnections
    For i = 0 to oPrinters.Count - 1 Step 2
        on error resume next
        aPrinter = split(uCase(oPrinters.Item(i+1)),"\\",-1, 1)
        if not UBound(aPrinter) = 0 then
            objNetwork.RemovePrinterConnection oPrinters.Item(i+1), True, True
            If Err.Number = 0 Then
                if showDebug = 1 Then
                    wscript.echo "Success: Removed printer: " & oPrinters.Item(i+1)
                End If
            else
                if showDebug = 1 Then
                    wscript.echo "Failed:  Removing printer: " & oPrinters.Item(i+1)
                end if
            end if
        end if
    next
end sub
