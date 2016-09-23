' Warning: This file is auto-generated and might be overwritten.
'          Please edit the following file instead:
' Warnung: Diese Datei wurde automatisch generiert und kann automatisch
'          überschrieben werden. Bitte bearbeiten Sie an Stelle dessen
'          die folgende Datei:
'
'         /usr/share/univention-printer-assignment/printer-assignment-template.vbs
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

' add printers and set default printer (to first printer)
if printerList <> "" Then
    items = split(printerList, " ")
    for i = 0 to UBound(items)
        if showDebug = 1 Then
            wscript.echo "Adding printer " & items(i)
        end if
        on error resume next
        objWshNetwork.AddWindowsPrinterConnection items(i)
    next
end if

' setting default printer
if defaultPrinter <> "" Then
    if showDebug = 1 Then
        wscript.echo "Set default printer to " & defaultPrinter
    end if
    on error resume next
    objWshNetwork.SetDefaultPrinter defaultPrinter
end if

if showDebug = 1 Then
    wscript.echo "Printer assignment finished."
end if

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
