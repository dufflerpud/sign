# Documentation for sign

Application to sign a document using Open-PGP and actually capture
a signature from the user's touchpad/mouse.

<hr>

<table src="src/*.cgi src/*.pl lib/*.js"><tr><th align=left><a href='#dt_872zbXSi7'>app.cgi</a></th><td>An application for Open-PGP signing a PDF file</td></tr>
<tr><th align=left><a href='#dt_872zbXSi8'>signature.js</a></th><td>Allow user to sign using touchpad or mouse</td></tr></table>

<hr>

<div id=docs>

## <a id='dt_872zbXSi7'>app.cgi</a>
An application for Open-PGP signing a PDF file
Adds user's signature entered through touchpad or mouse along
with QR code to document.

## <a id='dt_872zbXSi8'>signature.js</a>
Allow user to sign using touchpad or mouse
Heavily modified code from stackoverflow.com/users/242123/heycam
Most notable change is that all variables end up being part of sigp
to avoid name pollution.

Assumes you have setup a <svg> to work on.</div>

<hr>

If you add a file with #doc#/#indx# lines, you should make sure it will be
found in the 'table src=' line above and then rerun doc_sep in this directory.

Similarly, if you remove files, re-run doc_sep.


