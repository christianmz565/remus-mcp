Set xml = CreateObject("Msxml2.DOMDocument.3.0")
Set xsl = CreateObject("Msxml2.DOMDocument.3.0")
xml.async = False
xsl.async = False
xml.load WScript.Arguments(0)
xsl.load WScript.Arguments(1)
If xml.parseError.errorCode <> 0 Then
  WScript.Echo "XML Error: " & xml.parseError.reason
  WScript.Quit 1
End If
If xsl.parseError.errorCode <> 0 Then
  WScript.Echo "XSL Error: " & xsl.parseError.reason
  WScript.Quit 1
End If
WScript.Echo xml.transformNode(xsl)
