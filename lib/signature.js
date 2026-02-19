<script>
//
//indx#	signature.js - Allow user to sign using touchpad or mouse
//@HDR@	$Id$
//@HDR@
//@HDR@	Copyright (c) 2026 Christopher Caldwell (Christopher.M.Caldwell0@gmail.com)
//@HDR@
//@HDR@	Permission is hereby granted, free of charge, to any person
//@HDR@	obtaining a copy of this software and associated documentation
//@HDR@	files (the "Software"), to deal in the Software without
//@HDR@	restriction, including without limitation the rights to use,
//@HDR@	copy, modify, merge, publish, distribute, sublicense, and/or
//@HDR@	sell copies of the Software, and to permit persons to whom
//@HDR@	the Software is furnished to do so, subject to the following
//@HDR@	conditions:
//@HDR@	
//@HDR@	The above copyright notice and this permission notice shall be
//@HDR@	included in all copies or substantial portions of the Software.
//@HDR@	
//@HDR@	THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
//@HDR@	KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
//@HDR@	WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE
//@HDR@	AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
//@HDR@	HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
//@HDR@	WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
//@HDR@	FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
//@HDR@	OR OTHER DEALINGS IN THE SOFTWARE.
//
//hist#	2026-02-19 - Christopher.M.Caldwell0@gmail.com - Created
////////////////////////////////////////////////////////////////////////
//doc#	signature.js - Allow user to sign using touchpad or mouse
//doc#	Heavily modified code from stackoverflow.com/users/242123/heycam
//doc#	Most notable change is that all variables end up being part of sigp
//doc#	to avoid name pollution.
//doc#
//doc#	Assumes you have setup a <svg> to work on.
////////////////////////////////////////////////////////////////////////

var sigp = {};
var imgp;

//drawing functions
function DismissTouchEvent(e)
    {
    if( e.type.match(/^touch/) ) return e.preventDefault();
    }

function getCoords(e)
    {
    if( ! sigp.rect )
        { sigp.rect = sigp.panel_id.getBoundingClientRect(); }
    var cp = ( e.targetTouches ? e.targetTouches[0] : e );
    return (cp.clientX-sigp.rect.left)+','+(cp.clientY-sigp.rect.top);
    }

function pen_down(e)
    {
    sigp.string += ( 'M' + getCoords(e) + ' ' );
    sigp.pen_id.setAttribute('d', sigp.string);
    sigp.isDown = true;
    return DismissTouchEvent(e);
    }

function pen_move(e)
    {
    if (sigp.isDown)
	{
	sigp.string += ( 'L' + getCoords(e) + ' ' );
	sigp.pen_id.setAttribute('d', sigp.string);
	}
    return DismissTouchEvent(e);
    }

function pen_up(e)
    {
    sigp.isDown = false;
    return DismissTouchEvent(e);
    }

//helper functions
function clearSignature()
    {
    sigp.string = '';
    sigp.isDown = false;
    sigp.pen_id.setAttribute('d', sigp.string );
    }

function doneSignature()
    {
    window.document[sigp.form][sigp.sigtext].value = sigp.col+":"+sigp.row+":"+sigp.string;
    window.document[sigp.form].func.value = sigp.func;
    return window.document[sigp.form].submit();
    }

function clicked_on_document(e)
    {
    var clientp = ( e.targetTouches ? e.targetTouches[0] : e );
    var imrect = imgp.getBoundingClientRect();
    imrect.calc_width  = imrect.right  - imrect.left;
    imrect.calc_height = imrect.bottom - imrect.top;
    sigp.col = 100.0 * (clientp.clientX - imrect.left) / imrect.calc_width;
    sigp.row = 100.0 * (clientp.clientY - imrect.top ) / imrect.calc_height;
//    alert(	"imrect.left="		+imrect.left
//	+"\n"+	"imrect.right="		+imrect.right
//	+"\n"+	"imgp.clientLeft="	+imgp.clientLeft
//	+"\n"+	"imrect.calc_width="	+imrect.calc_width
//	+"\n"+	"clientp.clientX="	+clientp.clientX
//	+"\n"+	"sigp.col="		+sigp.col+"%\n"
//	+"\n"+	"imrect.bottom="	+imrect.bottom
//	+"\n"+	"imrect.top="		+imrect.top
//	+"\n"+	"imrect.calc_height="	+imrect.calc_height
//	+"\n"+	"clientp.clientY="	+clientp.clientY
//	+"\n"+	"sigp.row="		+sigp.row+"%" );

    (document.getElementById('signature_id')).style.display = '';
    (document.getElementById('document_id')).style.display = 'none';
    }

function setup_signature( formname, textvar, func )
    {
    sigp.form		= formname;
    sigp.sigtext	= textvar;
    sigp.func		= func
    sigp.panel_id	= document.getElementById('panel_id');
    sigp.pen_id		= document.getElementById('pen_id');
    sigp.rect_id	= document.getElementById('rect_id');

    clearSignature();

    sigp.rect_id.addEventListener('touchstart',	pen_down,	false);
    sigp.rect_id.addEventListener('touchmove',	pen_move,	false);
    sigp.rect_id.addEventListener('touchend',	pen_up,		false);
    sigp.rect_id.addEventListener('mousedown',	pen_down,	false);
    sigp.rect_id.addEventListener('mousemove',	pen_move,	false);
    sigp.rect_id.addEventListener('mouseup',	pen_up,		false);
    sigp.rect_id.addEventListener('mouseout',	pen_up,		false);

    imgp = document.getElementById("document_image_id");
    imgp.addEventListener('click', clicked_on_document, false);

    if( window.document[sigp.form].digital_signature.value == "none" )
        { (ebid("passphrase_prompt_id")).style.display = "none"; }
    }
</script>
