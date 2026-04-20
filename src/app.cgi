#!/usr/bin/perl -w
#
#indx#	app.cgi - An application for Open-PGP signing a PDF file
#@HDR@	$Id: app.cgi,v 1.1 2020/08/12 21:17:31 chris Exp chris $
#@HDR@
#@HDR@	Copyright (c) 2026 Christopher Caldwell (Christopher.M.Caldwell0@gmail.com)
#@HDR@
#@HDR@	Permission is hereby granted, free of charge, to any person
#@HDR@	obtaining a copy of this software and associated documentation
#@HDR@	files (the "Software"), to deal in the Software without
#@HDR@	restriction, including without limitation the rights to use,
#@HDR@	copy, modify, merge, publish, distribute, sublicense, and/or
#@HDR@	sell copies of the Software, and to permit persons to whom
#@HDR@	the Software is furnished to do so, subject to the following
#@HDR@	conditions:
#@HDR@	
#@HDR@	The above copyright notice and this permission notice shall be
#@HDR@	included in all copies or substantial portions of the Software.
#@HDR@	
#@HDR@	THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
#@HDR@	KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
#@HDR@	WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE
#@HDR@	AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
#@HDR@	HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#@HDR@	WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#@HDR@	FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
#@HDR@	OTHER DEALINGS IN THE SOFTWARE.
#
#hist#	2026-02-19 - Christopher.M.Caldwell0@gmail.com - Created
########################################################################
#doc#	app.cgi - An application for Open-PGP signing a PDF file
#doc#	Adds user's signature entered through touchpad or mouse along
#doc#	with QR code to document.
########################################################################

#########################################################################
#	Perl startup.							#
#########################################################################
use strict;
use MIME::Lite;
use Time::Local;
use JSON;
use Data::Dumper;
use List::Util qw(min max);

use lib "/usr/local/lib/perl";
use cpi_qrcode_of qw(qrcode_of);
use cpi_user qw(in_group logout_select can_admin);
use cpi_hash qw(hashof);
use cpi_setup qw(setup);
use cpi_help qw(help_strings);
use cpi_db qw( DBread DBwrite DBpop DBget DBput DBdelkey DBadd DBdel DBnewkey
 dbget dbread );
use cpi_file qw(cleanup fatal files_in fqfiles_in read_file read_lines
 tempfile write_file echodo mkdirp first_in_path );
use cpi_time qw(time_string);
use cpi_translate qw( xlate xlfatal xprint );
use cpi_english qw( plural );
use cpi_filename qw( text_to_filename filename_to_text );
use cpi_media qw( media_info );
use cpi_qrcode_of qw( qrcode_of );
use cpi_sortable qw( numeric_sort );
use cpi_perl qw( quotes );
use cpi_hash qw( hashof );
use cpi_inlist qw( inlist );
use cpi_template qw( template );
use cpi_send_file qw( sendmail );
use cpi_cgi qw( safe_html );
use cpi_vars;

$cpi_vars::TABLE_TAGS	= "bgcolor=\"#c0c0d0\"";
$cpi_vars::TABLE_TAGS	= "USECSS";

package main;

&setup(
	stderr=>"sign",
	Qrequire_captcha=>1,
	Qpreset_language=>"en",
	anonymous_funcs=>"qr,doc_viewanon"
	);

#########################################################################
#	Constant declarations.						#
#########################################################################

our $FORMNAME		= "form";
$cpi_vars::CACHEDIR 	= "$cpi_vars::BASEDIR/cache";
my $DOCUMENTS		= "$cpi_vars::BASEDIR/documents";
my $KEYS		= "$cpi_vars::BASEDIR/keys";
our $PROG_URL		= $cpi_vars::BASES_URL."/index.cgi";
$PROG_URL = $cpi_vars::BASES_URL."/index-test.cgi" if(($ENV{SCRIPT_NAME}||"") =~ /-test/);
my $PROJECT		= $cpi_vars::PROG;
my $LOGDIR		= "/var/log/$PROJECT";
my $YMDHM		= "%04d-%02d-%02d %02d:%02d";
my $STANDARD_DATE_FMT	= "%04d-%02d-%02d";
our $GLOBAL_TIME_FMT	= "%04d-%02d-%02dT%02d:%02d:%02d.000Z";
my $WKHTMLTOPDF		= "/usr/local/bin/wkhtmltopdf";
my $DISABLED		= "$cpi_vars::BASEDIR/disabled.html";
my $EXIT_FILE		= $cpi_vars::BASEDIR."/exit_reason.txt";
my $LIB_DIR		= $cpi_vars::BASEDIR."/lib";
my $SIGNATURE_JS	= $LIB_DIR."/signature.js";
my $SIGNATURE_HTML	= $LIB_DIR."/signature.html";
my $CVT			= "/usr/local/bin/nene";
my @KEY_TYPES		= ( "private", "public" );
my $form_top;
my $NEW_DOCUMENT	= "(New document)",
    
my $DEFAULT_WINDOW_SEARCH_MAX = 40;

my $NOW = time();

my @problems;

#########################################################################
#	Variable declarations.						#
#########################################################################

print STDERR "--- "
	. &time_string($YMDHM,$NOW)
	. " pid=$$ ---\n";
#print STDERR join("\n    ","Form:",
#	map { "$_=[$cpi_vars::FORM{$_}]" } sort keys %cpi_vars::FORM ), "\n"
#	if( %cpi_vars::FORM );

#########################################################################
#	Returns file modified string.					#
#	Doing a stat() is ugly, but if this is ever not element 9 the	#
#	world will seriously break.					#
#########################################################################
sub file_modified
    {
    return &time_string( $YMDHM, (stat($_[0]))[9] );
    }

#########################################################################
#	Used by the common administrative functions.			#
#########################################################################
sub footer
    {
    my( $mode ) = @_;

    $mode = "admin" if( !defined($mode) );

    my @toprint = (<<EOF );
<script>
function footerfunc( func0 )
    {
    with( window.document.footerform )
	{
	func.value = func0;
	submit();
	}
    }
</script>
<form name=footerform method=post>
<input type=hidden name=func>
<input type=hidden name=SID value="$cpi_vars::SID">
<input type=hidden name=USER value="$cpi_vars::USER">
<center class='no-print'><table $cpi_vars::TABLE_TAGS border=1>
<tr><th><table $cpi_vars::TABLE_TAGS><tr><th
EOF
    push( @toprint,
	"><input type=button help='index' onClick='show_help(\"index.cgi\");' value='XL(Help)'" );
    foreach my $button (
	( map {"${_}:XL($_)"} ("docs_show:Documents","keys_show:Digital keys")) )
        {
	my( $butdest, $buttext ) = split(/:/,$button);
	push( @toprint, "><input type=button onClick='do_submit(\"func\",\"$butdest\");'",
	    " help='search_$butdest'",
	    ( ($butdest eq $mode) ? " style='background-color:#50a0c0'" : "" ),
	    " value=\"$buttext\"\n" );
	}
    push( @toprint, ">",
	&logout_select(
	    "footerform",
	    "footerfunc"
	    ),<<EOF);
	</th></tr>
	</table></th></tr></table></center></form></div>
EOF
    &xprint( @toprint );
    }

#########################################################################
#	File to sign supplied on command line.  Put it in the user's	#
#	directory and then notify them.					#
#########################################################################
sub handoff
    {
    my( $destination_user, $file_to_sign, $mailto );
    &dbread( $cpi_vars::ACCOUNTDB );
    my $group = "sign_user";
    my %info;

    foreach my $arg ( @_ )
        {
	if( $arg =~ /@/ )
	    {
	    push( @problems, "E-mail address specified multiple times." )
	        if( $info{mailto} );
	    $info{mailto} = $arg;
	    }
	elsif( -r $arg )
	    {
	    push( @problems, "File specified multiple times." )
	        if( $file_to_sign );
	    $file_to_sign = $arg;
	    }
	elsif( &in_group( $arg, $group ) )
	    {
	    push( @problems, "Sign user specified multiple times." )
		if( $destination_user );
	    $destination_user = $arg;
	    }
	else
	    {
	    push( @problems, "Unknown argument [$arg]." );
	    }
	}

    push( @problems, "No file specified." ) if( ! $file_to_sign );
    push( @problems, "No user specified." ) if( ! $destination_user );
    &fatal( @problems ) if( @problems );

    my $email = &dbget( $cpi_vars::ACCOUNTDB, "users", $destination_user, "email" );
    push( @problems, "$destination_user does not have confirmed e-mail address." )
	if( ! $email
	 || ! &dbget( $cpi_vars::ACCOUNTDB, "users", $destination_user, "confirmemail" ) );
    &fatal(@problems) if( @problems );
    my $docname = $file_to_sign;
    $docname =~ s+.*/++;
    $docname =~ s/\.[^\.]*$//;
    my $base = "$DOCUMENTS/$destination_user/$docname";
    my $destname = "$base.unsigned.pdf";
    my $info_file = "$base.info.po";
    my $doctextname = &filename_to_text($docname);
    &fatal("$destname already exists.") if( -e $destname );
    if( $file_to_sign =~ /\.pdf$/ )
	{ &echodo("cp '$file_to_sign' '$destname'"); }
    else
	{ &echodo("$CVT -v1 '$file_to_sign' '$destname'"); }
    &fatal("Could not make $destname from $file_to_sign.")
	if( ! -s $destname );
    &write_file( $info_file,
	Data::Dumper->Dump( [ \%info ], [ qw(*info) ] ) );
    chmod( 0666, $info_file );
    $cpi_vars::USER ||= $ENV{LOGNAME};
    my $subject =
	"\"$doctextname\" received from "
	. &dbget($cpi_vars::ACCOUNTDB,"users",$cpi_vars::USER,"fullname")
	. " for signature.";
    print "E-mail from $cpi_vars::DAEMON_EMAIL to [$email]:  $subject\n";
    &sendmail( $cpi_vars::DAEMON_EMAIL,
	$email,
	$subject,
	"<html><head></head><body><h2>Click <a href='$cpi_vars::URL'>here</a> to sign \"$doctextname\" document.</h2></body></html>",
	$destname );
    &cleanup(0);
    }

#########################################################################
#	We're not a web program.  Triage!				#
#########################################################################
sub non_CGI_handler
    {
    if( ! defined($ARGV[0]) )
	{ push(@problems,"No arguments specified."); }
    elsif( $ARGV[0] eq "handoff" )	{ &handoff( @ARGV[1..$#ARGV] );	}
    elsif( $ARGV[0] eq "export" )	{ &export_all( $ARGV[1]);	}
    elsif( $ARGV[0] eq "import" )	{ &import_all( $ARGV[1]);	}
    else
	{ push(@problems,"Unknown argument '$ARGV[0]' specified."); }

    &xlfatal("XL(Usage):  $cpi_vars::PROG.cgi (dump|dumpaccounts|dumptranslations|undump|undumpaccounts|undumptranslations) [ dumpname ]")
   	 if( @problems );
    }

#########################################################################
#	Return the top of the page.					#
#########################################################################
sub app_top
    {
    return <<EOF;
</head><body $cpi_vars::BODY_TAGS>
$cpi_vars::HELP_IFRAME
<div id=body_id>
<form name=$FORMNAME method=post ENCTYPE="multipart/form-data">
<input type=hidden name=func>
<input type=hidden name=arg>
<input type=hidden name=SID value="$cpi_vars::SID">
<input type=hidden name=USER value="$cpi_vars::USER">
<center>
EOF
    }

#########################################################################
#	Return table entries for messages.				#
#########################################################################
sub messages
    {
    my( $columns, @msgs ) = @_;
    my @toprint;
    push( @toprint, "<tr><th colspan=$columns><table border=0><tr><td><b>",
	join("<br>",@msgs), "</b></td></tr></table></th></tr>\n" )
	if( @msgs );
    return @toprint;
    }

#########################################################################
#	Print out results of search showing all signed documents so	#
#	far.								#
#########################################################################
sub func_docs_show
    {
    my( @msgs ) = @_;
    my @toprint =
	(
	&app_top(),
	"<input type=hidden name=what>\n",
	"<input type=hidden name=new_name id=new_name_id>",
	"<input type=file name=new_contents id=new_contents_id",
	" onChange='(ebid(\"new_name_id\")).value=prompt(\"XL(Enter key name):\",this.value.replace(/.*\\\\/,\"\").replace(/\\..*/,\"\"));do_submit(\"func\",\"doc_upload_unsigned\");'",
	" style='display:none'>\n"
	);
    my $directory = "$DOCUMENTS/$cpi_vars::USER";
    &mkdirp( 0755, $directory, "$KEYS/$cpi_vars::USER" );
    my %seen_file_base;
    foreach my $files_in ( &files_in( $directory ) )
	{
	$seen_file_base{$1}{2} = 1
	    if( $files_in =~ /(.*)\.(unsigned|signed).pdf$/ );
	}
    my @files =
        (
	$NEW_DOCUMENT,
	&numeric_sort(
	    grep( ! $seen_file_base{$_}{signed}, keys %seen_file_base ) ),
	&numeric_sort(
	    grep(   $seen_file_base{$_}{signed}, keys %seen_file_base ) )
	);

    push( @toprint, "<table border=1 style='border-collapse:collapse'>" );
#    foreach my $k ( sort keys %cpi_vars::FORM )
#	{ push( @toprint, "<tr><th align=left>$k</th><td>$cpi_vars::FORM{$k}</td></tr>\n" ); }
    push( @toprint, &messages(3,@msgs) );
    if( ! @files )
	{ push( @toprint, "<tr><th colspan=3>No documents found</th></tr>\n" ); }
    else
	{
        push(@toprint,
	    "<input type=hidden name=destination>",
	    "<tr><th>XL(Document)</th>",
		"<th>XL(Unsigned)</th>",
		"<th>XL(Signed)</th></tr>\n");
	foreach my $base ( @files )
	    {
	    my $info_file="$directory/$base.info.po";
	    my $signed_datetime;
	    my %info;
	    if( -r $info_file )
		{
		eval( &read_file( $info_file ) );
		$signed_datetime =
		    &time_string($YMDHM,$info{signed});
		}
	    push( @toprint, "<tr><th align=left>",
		&filename_to_text($base), "</th>" );
	    foreach my $ftype ( "unsigned", "signed" )
	        {
		push( @toprint, "<th>" );
		my $fname = "$directory/$base.$ftype.pdf";
		my $maildest = $info{mailto} || "";
		if( -r $fname )
		    {
		    my $modified = &file_modified($fname);
		    push( @toprint,
			"<select onChange='",
			"if(this.value==\"doc_send\"){do_submit(\"func\",this.value,\"what\",\"$base.$ftype\",\"destination\",prompt(\"XL(Send file to what address?)\",\"$maildest\"));} else if(this.value!=\"doc_del\"||confirm(\"XL(Are you sure you want to delete $ftype) $base?\")){do_submit(\"func\",this.value,\"what\",\"$base.$ftype\");}this.selectedIndex=0;'>",
			"<option disabled selected>$modified</option>");
		    foreach my $buttext (
			"doc_info:Information",
			"doc_view:View",
			"doc_download:Download",
			"doc_send:Send e-mail",
			"doc_del:Delete" )
			{
			my( $but, $text ) = split(/:/,$buttext);
			push( @toprint,
			    "<option value=\"$but\">XL($text)</option>\n" );
			}
		    push( @toprint, "</select>" );
		    }
		elsif( $ftype eq "unsigned" )
		    {
		    push( @toprint, "<input type=button value='XL(Upload)'",
		    	" onClick='(ebid(\"new_contents_id\")).click();'>" );
		    }
		elsif( $ftype eq "signed" )
		    {
		    push( @toprint,
			"<select name=digital_signature onChange='",
			( $base eq $NEW_DOCUMENT
			    ? "(ebid(\"new_contents_id\")).click();"
			    : "do_submit(\"func\",\"doc_sign\",\"what\",\"$base\");" ),
			"'>",
			"<option disabled selected>",
			( $base eq $NEW_DOCUMENT
			    ? "XL(Upload and sign)"
			    : "XL(Sign)" ),
			"</option>" );
		    foreach my $sigbase ( &files_in( "$KEYS/$cpi_vars::USER", ".*\\.private\\.asc" ) )
			{
			my $text = &filename_to_text($sigbase);
			$text =~ s/\.private$//;
			push( @toprint,
			    "<option value='$sigbase'>$text</option>\n" );
			}
		    push( @toprint, "<option value=none>No digital signature</option>",
			"</select>" );
		    if( $ENV{HTTP_USER_AGENT}=~/Safari/
		     && $base eq $NEW_DOCUMENT )
		        {
			push( @toprint,
			    "<input type=button value='XL(Upload)' onClick='",
			    ( $base eq $NEW_DOCUMENT
				? "(ebid(\"new_contents_id\")).click();"
				: "do_submit(\"func\",\"doc_sign\",\"what\",\"$base\");" ),
			    "'>");
			}
		    }
		push( @toprint, "</th>" );
		}
	    push( @toprint, "</tr>" );
	    }
	}
    push( @toprint,"</table></form>\n");
    &xprint( @toprint );
    &footer("docs_show");
    &cleanup(0);
    }

#########################################################################
#	Return a graphic from the signature script.			#
#########################################################################
sub rescale_and_draw
    {
    my( $analog_from, $analog_to,
	$analog_signature,
	$offsetcol, $offsetrow,
	$scalecol, $scalerow ) = @_;
    my $sign_line_height = 10;
    my $sign_line_length = 180;
    my( $mincol, $maxcol, $minrow, $maxrow );
    print STDERR "Parsing [$analog_signature]\n";
    my @toks = split(/\s/,$analog_signature);
    foreach my $ins ( @toks )
	{
	if( $ins =~ /^([ML])([\d\.]+),([\d\.]+)$/ )
	    {
	    if( ! defined($mincol) )
		{ $mincol=$maxcol=$2; $minrow=$maxrow=$3; }
	    else
		{
		if($2<$mincol) {$mincol=$2;} elsif($2>$maxcol) {$maxcol=$2;}
		if($3<$minrow) {$minrow=$3;} elsif($3>$maxrow) {$maxrow=$3;}
		}
	    }
	}

    my $colfac = $scalecol / ( $maxcol-$mincol+0.0 );
    my $rowfac = $scalerow / ( $maxrow-$minrow+0.0 );

    print STDERR "colfac($colfac)=scalecol($scalecol)/(maxcol($maxcol)-mincol($mincol))\n";
    print STDERR "rowfac($rowfac)=scalerow($scalerow)/(maxrow($maxrow)-minrow($minrow))\n";

    my @ppmdraw_cmds = ( "setcolor black;\n" );
    push( @ppmdraw_cmds,
	sprintf("text %d %d %d 0 \"Signed %s\";\n",
	    $offsetcol, ($offsetrow+$scalerow-$sign_line_height-5),
	    $sign_line_height,
	    &time_string($YMDHM,$NOW) ) );
    my $currow = 0;
    my $curcol = 0;
    foreach my $ins ( @toks )
	{
	if( $ins =~ /^([ML])([\d\.]+),([\d\.]+)$/ )
	    {
	    my $fnc = ( $1 eq "M" ? "setpos" : "line_here" );
	    my $newcol = int( $colfac * ( $2 - $mincol ) ) + $offsetcol;
	    my $newrow = int( $rowfac * ( $3 - $minrow ) ) + $offsetrow;
	    if( $1 eq "M" )
		{ push( @ppmdraw_cmds, "setpos $newcol $newrow;\n" ); }
	    else
		{
		push( @ppmdraw_cmds, sprintf("line_here %d %d;\n",
		    ($newcol-$curcol),($newrow-$currow) ) );
		}
	    $curcol = $newcol;
	    $currow = $newrow;
	    }
	}
    my $script_name = &tempfile(".script");
    &write_file( $script_name, @ppmdraw_cmds );
    &echodo("ppmdraw -scriptfile='$script_name' < '$analog_from' > '$analog_to'");
    return $analog_to;
    }

#########################################################################
#	Setup for user to sign existing document.			#
#########################################################################
sub func_doc_sign
    {
    my $unsigned = "$DOCUMENTS/$cpi_vars::USER/$cpi_vars::FORM{what}.unsigned.pdf";
    my $doc_as_jpg_b64 = &read_file("$CVT '$unsigned' -.jpeg|base64 -w 0 |");

    #my @toprint = ( &app_top() );
    &xprint(
	&read_file( $SIGNATURE_JS ),
	&app_top(),
	&template( $SIGNATURE_HTML,
	    "%%DOCUMENT_JPG%%", $doc_as_jpg_b64,
	    "%%PASSPHRASE_PLACEHOLDER%%",
		"Passphrase for $cpi_vars::FORM{digital_signature} private key" ),
	"<input type=hidden name=analog_signature>",
	"<input type=hidden name=what value='$cpi_vars::FORM{what}'>",
	"<input type=hidden name=digital_signature value='$cpi_vars::FORM{digital_signature}'>",
	"</form>",
	"<script>setup_signature('$FORMNAME','analog_signature','doc_signed' );</script>\n");
    &footer("docs_show");
    &cleanup(0);
    }

#########################################################################
#	Incoming file.							#
#########################################################################
sub func_doc_upload_unsigned
    {
    my $name		= &text_to_filename($cpi_vars::FORM{new_name});
    my $unsigned	= "$DOCUMENTS/$cpi_vars::USER/$name.unsigned.pdf";

    if( $cpi_vars::FORM{new_contents} =~ /^%PDF/ )
	{
	print STDERR "Uploading PDF file into $unsigned.\n";
	&write_file( $unsigned, $cpi_vars::FORM{new_contents} );
	}
    else
        {
	my $uploading = &tempfile(".unknown");
	&write_file( $uploading, $cpi_vars::FORM{new_contents} );
	&echodo("$CVT -v1 '$unsigned' < '$uploading'");
	}
    if( ! $cpi_vars::FORM{digital_signature} )
        { &func_docs_show("$unsigned uploaded."); }
    else
        {
	$cpi_vars::FORM{what} = $name;
	&func_doc_sign();
	}
    }

#########################################################################
#	Incoming file.							#
#########################################################################
sub func_doc_signed
    {
    my $SIGNATURE_COLS		= 200;
    my $SIGNATURE_ROWS		= 50;
    my $name			= &text_to_filename($cpi_vars::FORM{what});
    my $relative_file		= $cpi_vars::USER."/".&text_to_filename($name);
    my $base_file		= "$DOCUMENTS/$relative_file";
    my $unsigned		= "$base_file.unsigned.pdf";
    my $signed			= "$base_file.signed.pdf";
    my $info_file		= "$base_file.info.po";
    my $cookie;

    my @msgs;
#    foreach my $var ( sort keys %cpi_vars::FORM )
#	{ push(@msgs,"$var = [$cpi_vars::FORM{$var}]"); }

    $cpi_vars::VERBOSITY=1;

    &DBwrite();
    do { $cookie = &hashof(rand()); } while ( &DBget("ck_$cookie") );
    &DBput("ck_$cookie",$relative_file);
    &DBpop();
    
    my $tempdir = "$cpi_vars::BASEDIR/draw";
    $tempdir = &tempfile(".breakout") if( ! -d $tempdir );
    system("rm -rf $tempdir");
    my $qrcode_file = "$tempdir/qrcode.pnm";
    my $pre_qrcode_pages = "$tempdir/pre_qrcode_pages";
    my $pre_analog_pages = "$tempdir/pre_analog_pages";
    my $post_stamped_pages = "$tempdir/post_stamped_pages";
    my( $colpct, $rowpct, $analog_signature )
	= split(/:/,$cpi_vars::FORM{analog_signature});
    my $generic_page_info;

    &mkdirp( 0755, $pre_qrcode_pages, $pre_analog_pages, $post_stamped_pages );

    &qrcode_of(
	"$cpi_vars::URL?func=qr&c=$cookie",
	{ type=>"pnm", file=>$qrcode_file } );
    my $qr_info = &media_info( $qrcode_file );

    &echodo( "pdftoppm '$unsigned' '$pre_qrcode_pages/X'" );
    my @to_unite;
    my $page_start = 0;
    foreach my $pagename ( &numeric_sort(&files_in($pre_qrcode_pages)) )
	{
	$generic_page_info = &media_info("$pre_qrcode_pages/$pagename")
	    if( ! defined($generic_page_info) );
	my $page_end = $page_start + $generic_page_info->{height};
	my $page_col = int($colpct * $generic_page_info->{width} / 100.0);
	my $page_row = int($rowpct * $generic_page_info->{height} / 100.0);
	if( $page_row < 0 || $page_row > $generic_page_info->{height} )
	    {
	    &echodo( &quotes(
		"cp",
		"$pre_qrcode_pages/$pagename",
		"$post_stamped_pages/$pagename") );
	    }
	else
	    {
	    my $relative_row = $page_row - $page_start;
	    &echodo("pamcomp -xoff=$page_col -yoff=".int($relative_row-$qr_info->{height}),
		&quotes(
		    $qrcode_file,
		    "$pre_qrcode_pages/$pagename",
		    "$pre_analog_pages/$pagename" ) );
	    &rescale_and_draw(
		"$pre_analog_pages/$pagename",
		"$post_stamped_pages/$pagename",
		$analog_signature,
		$page_col+$qr_info->{width}, $relative_row-$SIGNATURE_ROWS,
		$SIGNATURE_COLS, $SIGNATURE_ROWS );
	    }
	
	# For reasons I do not understand ps2pdf is very slow operating on stdin
	&echodo("pnmtops -noturn < '$post_stamped_pages/$pagename' > '$post_stamped_pages/$pagename.ps'");
	&echodo("ps2pdf '$post_stamped_pages/$pagename.ps' '$post_stamped_pages/$pagename.pdf'");
        push( @to_unite, "$post_stamped_pages/$pagename.pdf" );
	$page_start = $page_end;
	}

    my $pre_digital_sign = &tempfile(".pdf");
    &echodo("pdfunite", &quotes( @to_unite, $pre_digital_sign ) );

    if( $cpi_vars::FORM{digital_signature} eq "none" )
        { &echodo( &quotes("cp",$pre_digital_sign,$signed) ); }
    else
	{
	my $digital_file = "$KEYS/$cpi_vars::USER/$cpi_vars::FORM{digital_signature}";
	my $pgp = &first_in_path("pgp","rnp","gpg");
	if( $pgp =~ /gpg/ )
	    {
	    my $pgp_homedir = &tempfile(".pgp_homedir");
	    &mkdirp( 0700, $pgp_homedir );
	    my @gpg_prefix =
		(
		$pgp,
		"--quiet --lock-never --batch",
		"--homedir", $pgp_homedir
		);
	    my @cmd1 = ( @gpg_prefix, "--import", &quotes($digital_file) );
	    my @cmd2 = ( @gpg_prefix,
		"--passphrase", &quotes( $cpi_vars::FORM{passphrase} ),
		"--pinentry-mode loopback -armor --clearsign",
		"--output", &quotes($signed),
		"--", &quotes($pre_digital_sign ) );
	    print STDERR "Executing [",join(" ",@cmd1),"]\n";
	    &echodo( @cmd1 );
	    print STDERR "Executing [",join(" ",@cmd2),"]\n";
	    &echodo( @cmd2 );
	    }
	else
	    {
	    my @to_exec = ( $pgp,
		"--armor --clearsign",
		"--keyfile",	&quotes($digital_file),
		"--output",	&quotes($signed),
		"--password",	&quotes($cpi_vars::FORM{passphrase}),
		$pre_digital_sign );
	    print STDERR "About to execute [",join(" ",@to_exec),"]\n";
	    &echodo( @to_exec );
	    }
	}

    if( ! -r $signed )
        { push(@msgs,
	    "XL(Signature failure, probably due to passphrase mismatch.)"); }
    else
	{
	my %info;
	eval( &read_file( $info_file ) ) if( -r $info_file );
	$info{name}			= $name;
	$info{user}			= $cpi_vars::USER." ("
					    .	&dbget($cpi_vars::ACCOUNTDB,
						"users",$cpi_vars::USER,"fullname")
					    . ")";
	$info{signed}			= $NOW;
	$info{digital_signature}	= $cpi_vars::FORM{digital_signature};
	$info{size}			= -s $signed;
	$info{agent}			= $ENV{HTTP_USER_AGENT};
	$info{remote_addr}		= $ENV{REMOTE_ADDR};
	$info{analog_location}		= join(",",$colpct,$rowpct);
	$info{cookie}			= $cookie;
	&write_file( $info_file,
	    Data::Dumper->Dump( [ \%info ], [ qw(*info) ] ) );
	push( @msgs, "$unsigned uploaded");
	}
    &func_docs_show(@msgs);
    }

#########################################################################
#	Return the output of an attempt at verifying the digital	#
#	signature of a file.						#
#########################################################################
sub verify
    {
    my @ret = &read_lines("gpg --quiet --lock-never --batch --homedir /tmp --keyserver-options auto-key-retrieve --no-auto-check-trustdb --verify $_[0] 2>&1 |");
    return join("\n",grep(! /with a trusted/, grep(! /no indication/, @ret )));
    }

#########################################################################
#	Generate a string containing a table of info about the file	#
#	which may be presented directly to the user or e-mailed to him.	#
#########################################################################
sub gen_info_table
    {
    my( $base_file ) = @_;
    $base_file =~ s/\.(pdf|po)$//;
    $base_file =~ s/\.(unsigned|signed|info)$//;
    my %fnames =
        (
	unsigned	=>	$base_file.".unsigned.pdf",
	signed		=>	$base_file.".signed.pdf",
	info		=>	$base_file.".info.po"
	);
    my @toprint = ( "<table style='border-collapse:collapse'>" );

    if( ! -r $fnames{info} )
        {
	push( @toprint,
	    "<tr><th valign=top align=left>XL(Document name):</th>",
		"<td>$fnames{unsigned}</td></tr>",
	    "<tr><th valign=top align=left>XL(Uploaded):</th>",
	        "<td>",&file_modified($fnames{unsigned}),"</td></tr>" );
	}
    else
	{
        my %info;
	eval( &read_file( $fnames{info} ) );
	my $kuser = $info{user};
	$kuser =~ s/ .*//;
	my $kbase = $info{digital_signature};
	$kbase =~ s/\.private\.asc//;
	my $public_key = join( "/", $KEYS, $kuser, $kbase.".public.asc" );
	$cpi_vars::FORM{c} ||= $info{cookie};
	push( @toprint,
	    "<input type=hidden name=c value='",$info{cookie},"'>",
	    "<tr><th valign=top align=left>XL(Document name):</th>",
	        "<td valign=top>",
	         "<a href='$cpi_vars::URL?func=doc_viewanon&c=$info{cookie}'>",
		&filename_to_text($info{name}),"</a></td></tr>",
	    "<tr><th valign=top align=left>XL(Signing user):</th>",
		"<td valign=top>",$info{user},"</td></tr><tr>",
	    "<tr><th valign=top align=left>XL(Signed):</th>",
		"<td valign=top>", &time_string($YMDHM,$info{signed}), "</td></tr>",
	    "<tr><th valign=top align=left>XL(Agent):</th>",
		"<td valign=top>",$info{agent},"</td></tr>",
	    "<tr><th valign=top align=left>XL(Agent IP):</th>",
		"<td valign=top>",$info{remote_addr},"</td></tr>",
	    "<tr><th valign=top align=left>XL(Size in bytes):</th>",
		"<td valign=top>",$info{size},"</td></tr>",
	    "<tr><th valign=top align=left>XL(Send signed document to):</th>",
		"<td valign=top>",$info{mailto}||"","</td></tr>",
	    "<tr><th valign=top align=left>XL(Digital signature):</th>",
		"<td valign=top>",&filename_to_text($kbase),"<br>",
		( ! -r $public_key
		? "XL(Public key unavailable here)"
		: ("<pre>", &read_file($public_key), "</pre>" )),
		"</td></tr>",
	    "<tr><th valign=top align=left>XL(Verification):</th>",
		"<td>",
		( ! -r $fnames{signed} )
		? "XL(No verification possible)"
		: ("<pre>", &safe_html(&verify($fnames{signed})), "</pre>"),
		"</td></tr>");
	}
    push( @toprint, "</table>" );
    return join("",@toprint);
    }

#########################################################################
#	Dump an info file.						#
#########################################################################
sub info_table
    {
    my( $base_file ) = @_;
    &xprint( &app_top(), &gen_info_table(@_), "</form>" );
    }

#########################################################################
#	Show the signing information.					#
#########################################################################
sub func_doc_info
    {
    &info_table(join("/",$DOCUMENTS,$cpi_vars::USER,$cpi_vars::FORM{what}));
    &footer("docs_show");
    &cleanup(0);
    }

#########################################################################
#	Delete the files starting with $base_file.			#
#########################################################################
sub delete_base
    {
    my( $base_file ) = @_;
    my @msgs;
    foreach my $fname ( glob("$base_file.*" ) )
	{
	push( @msgs,
	    ( unlink($fname)
	    ? "$fname XL(deleted.)"
	    : "$fname XL(deletion failed):  $!" ) );
	}
    return @msgs;
    }

#########################################################################
#	Delete all the files associated with the base.			#
#########################################################################
sub func_doc_del
    {
    &func_docs_show(
	&delete_base(
	    join("/",$DOCUMENTS,$cpi_vars::USER,$cpi_vars::FORM{what})))
    }

#########################################################################
#	If we're doing a doc view, we're going to send a PDF header.	#
#########################################################################
sub check_if_app_needs_header
    {
    return ( ! &inlist( $cpi_vars::FORM{func}, "doc_view", "doc_viewanon", "doc_download" ) );
    }

#########################################################################
#	Output the pdf file
#########################################################################
sub view_pdf
    {
    my( $to_view, $base_file ) = @_;
    &fatal("Cannot find $to_view.") if( ! -r $to_view );
    my @toprint = ( "Content-type:  application/pdf\n" );
    push( @toprint,
	"Content-disposition: attachment; filename=\"$base_file\"\n" )
	    if( $cpi_vars::FORM{func} eq "doc_download" );
    print @toprint, "\n", &read_file($to_view);
    &cleanup(0);
    }

#########################################################################
#	Allow anonymous user to view file.				#
#########################################################################
sub func_doc_viewanon
    {
    my $relative_file = &DBget("ck_$cpi_vars::FORM{c}");
    &fatal("Malformed cookie.") if( ! $relative_file );
    my $to_view = join("/",$DOCUMENTS,$relative_file.".signed.pdf");
    my $base_file = $to_view;
    $base_file =~ s+.*/++;
    &view_pdf( $to_view, $base_file );
    &cleanup(0);
    }

#########################################################################
#	Allow user to view signed pdf file.				#
#	A document download is just a document view but specifies a	#
#	name for file to download.					#
#########################################################################
sub func_doc_view
    {
    my $base_file = $cpi_vars::FORM{what}.".pdf";
    my $to_view = join("/",$DOCUMENTS,$cpi_vars::USER,$base_file);
    &view_pdf( $to_view, $base_file );
    }
sub func_doc_download { &func_doc_view(); }

#########################################################################
#	Some pour soul has clicked on a signature QR code.		#
#########################################################################
sub func_qr
    {
    my $relative_file = &DBget("ck_$cpi_vars::FORM{c}");
    &fatal("Malformed QR code.") if( ! $relative_file );
    &xprint( &app_top(), &gen_info_table("$DOCUMENTS/$relative_file") );
    &cleanup(0);
    }

#########################################################################
#	E-mail signed document to the specified address.		#
#########################################################################
sub func_doc_send
    {
    my $base_file = join("/",$DOCUMENTS,$cpi_vars::USER,$cpi_vars::FORM{what});
    my $to_send = $base_file.".pdf";
    my @subject = (&dbget($cpi_vars::ACCOUNTDB,"users",$cpi_vars::USER,"fullname") );
    my @toprint = ("<html><body>",&gen_info_table($to_send),"</body></html>");
    my @msgs;
    my $info_file = $base_file;
    $info_file =~ s/\.(unsigned|signed)$/.info.po/;
    if( -r $info_file )
	{
	my %info;
	eval( &read_file( $info_file ) );
	push( @subject,
	    "signed",
	    $info{name},
	    &time_string( $YMDHM, $info{signed} )
	    );
        push( @msgs, "XL(Signed) '$info{name}' XL(sent to) $cpi_vars::FORM{destination}" );
	}
    else
        {
	push( @subject, "uploaded", $to_send,
	    &time_string( $YMDHM, &file_modified($to_send) ) );
        push( @msgs, "$to_send XL(sent to) $cpi_vars::FORM{destination}" );
	}
    &sendmail( $cpi_vars::DAEMON_EMAIL,
	$cpi_vars::FORM{destination},
	join(" ",@subject),
	&xlate(join("\n",@toprint)),
	$to_send );
    &func_docs_show( @msgs );
    }

#########################################################################
#	Show all the signatures.					#
#########################################################################
sub func_keys_show
    {
    my( @msgs ) = @_;
    my( @toprint ) = &app_top();
    my $directory = "$KEYS/$cpi_vars::USER";
    my %seen_file_base;
    my $columns = scalar(@KEY_TYPES) + 1;
    &mkdirp( 0755, $directory );
    foreach my $fname ( &files_in( $directory ) )
	{
	$seen_file_base{$1}{$2}=1 if( $fname =~ /(.*)\.(private|public).asc$/ );
	}
    my @files = sort keys %seen_file_base;

    push( @toprint,
	"<input type=hidden name=what>",
        "<table border=1 style='border-collapse:collapse'>" );
#    foreach my $k ( sort keys %cpi_vars::FORM )
#	{ push( @toprint, "<tr><th align=left>$k</th><td>$cpi_vars::FORM{$k}</td></tr>\n" ); }
    push( @toprint, &messages($columns,@msgs) );
    if( ! @files )
	{ push( @toprint, "<tr><th>No signatures found</th></tr>\n" ); }
    else
	{
        push(@toprint,"<tr><th>XL(Key name)</th>");
	foreach my $ktype ( @KEY_TYPES )
	    {
	    push( @toprint, "<th>XL(".ucfirst($ktype)." key)</th>");
	    }
	push( @toprint, "</tr>\n" );
	foreach my $base ( @files )
	    {
	    push( @toprint, "<tr><th align=left>",
		&filename_to_text($base), "</th>" );
	    foreach my $ktype ( @KEY_TYPES )
	        {
		push( @toprint,"<th>");
		if( ! $seen_file_base{$base}{$ktype} )
		    { push( @toprint, "XL(No $ktype key)" ); }
		else
		    {
		    push( @toprint,
			"<select onChange='",
			"if(this.value!=\"key_del\"||confirm(\"XL(Are you sure you want to delete the $ktype key for) $base?\")){do_submit(\"func\",this.value,\"what\",\"$base.$ktype\");}this.selectedIndex=0;'>",
			"<option disabled selected>XL(Option)</option>");
		    foreach my $buttext (
			"key_info:Information",
			"key_del:Delete" )
			{
			my( $but, $text ) = split(/:/,$buttext);
			push( @toprint,
			    "<option value=\"$but\">XL($text)</option>\n" );
			}
		    push( @toprint, "</select>" );
		    }
		push( @toprint, "</th>" );
		}
	    push( @toprint, "</tr>" );
	    }
	}
    push( @toprint, "<tr><th colspan=$columns>",
	"<input type=hidden name=new_name id=new_name_id style='display:none'>",
	"<input type=file name=new_contents id=new_contents_id style='display:none'",
	" onChange='(ebid(\"new_name_id\")).value=prompt(\"XL(Enter key name):\",this.value.replace(/.*\\\\/,\"\").replace(/\\..*/,\"\"));do_submit(\"func\",\"key_upload\");'>",
	"<input type=button value='XL(Upload private or public key)'",
	" onClick='(ebid(\"new_contents_id\")).click();'>",
	"</table></form>" );
    &xprint( @toprint );
    &footer("keys_show");
    &cleanup(0);
    }

#########################################################################
#	Incoming file.							#
#########################################################################
sub func_key_upload
    {
    my( $name ) = &text_to_filename($cpi_vars::FORM{new_name});
    my $directory = "$KEYS/$cpi_vars::USER";
    my @msgs;

    my $ktype =
        ( $cpi_vars::FORM{new_contents} =~ /BEGIN PGP PRIVATE KEY BLOCK/
	? "private"
        : $cpi_vars::FORM{new_contents} =~ /BEGIN PGP PUBLIC KEY BLOCK/
	? "public"
	: "unknown" );
    if( $ktype eq "unknown" )
        { push( @msgs, "XL(Cannot identify file contents for) \"$name\"." ); }
    else
        {
	&mkdirp( $directory );
	&write_file( "$directory/$name.$ktype.asc",
	    $cpi_vars::FORM{new_contents} );
	push( @msgs, "\"$name\" XL(uploaded as a $ktype key.)" );
	}
    &func_keys_show(join("<br>",@msgs));
    }

#########################################################################
#	Show information about a signature file				#
#########################################################################
sub func_key_info
    {
    my $base_file = join("/",$KEYS,$cpi_vars::USER,$cpi_vars::FORM{what}).".asc";
    &fatal("$base_file does not exist.") if( ! -r $base_file );
    &xprint(
	&app_top(),
	"<table><tr><td><pre>",
	&read_file( $base_file ),
	"</pre></td></tr></table>",
	"</form>" );
    &footer("keys_show");
    &cleanup(0);
    }

#########################################################################
#	Delete signatures.						#
#########################################################################
sub func_key_del
    {
    &func_keys_show(
	&delete_base(
	    join("/",$KEYS,$cpi_vars::USER,$cpi_vars::FORM{what})));
    }

#########################################################################
#	We've decided we're a web program.  Triage!			#
#########################################################################
sub CGI_handler
    {
    #print "Content-type:  text/html\n\nFORM=$cpi_vars::FORM{USER} USER=$cpi_vars::USER.<br>";
    $cpi_vars::USER ||= "anonymous";
    $form_top = &app_top();
    $cpi_vars::FORM{func} ||= "docs_show";
    $cpi_vars::FORM{func} = "docs_show" if($cpi_vars::FORM{func} eq "dologin");
    if( exists &{"func_$cpi_vars::FORM{func}"} )
	{ __PACKAGE__->can("func_$cpi_vars::FORM{func}")->(); }
    else
	{ &func_docs_show( "Unknown func [$cpi_vars::FORM{func}]" ); }
    }

#########################################################################
#	Main								#
#########################################################################

$Data::Dumper::Sortkeys = 1;
if( ! defined($ENV{SCRIPT_NAME}) || $ENV{SCRIPT_NAME} eq "" )
    { &non_CGI_handler(); }
elsif( $ENV{SCRIPT_NAME}!~/.*-test/ && -r $DISABLED )
    { print &read_file( $DISABLED ); }
else
    { &CGI_handler(); }
&cleanup(0);
