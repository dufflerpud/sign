#!/usr/bin/perl -w
#@HDR@	$Id: app.cgi,v 1.1 2020/08/12 21:17:31 chris Exp chris $
#@HDR@		Copyright 2026 by
#@HDR@		Christopher Caldwell/Brightsands
#@HDR@		P.O. Box 401, Bailey Island, ME 04003
#@HDR@		All Rights Reserved
#@HDR@
#@HDR@	This software comprises unpublished confidential information
#@HDR@	of Brightsands and may not be used, copied or made available
#@HDR@	to anyone, except in accordance with the license under which
#@HDR@	it is furnished.
#########################################################################
#	sign.cgi							#
#		2024-04-18	c.m.caldwell@alumni.unh.edu		#
#									#
#	Create routes for drivers for meal delivery service.		#
#									#
#	Tested with:							#
#		Meals-on-wheels						#
#		Harpswell Aging	at Home					#
#########################################################################

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
 dbget );
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

#########################################################################
#	Variable declarations.						#
#########################################################################

print STDERR "--- "
	. &time_string($YMDHM,$NOW)
	. " pid=$$ ---\n";
print STDERR join("\n    ","Form:",
	map { "$_=[$cpi_vars::FORM{$_}]" } sort keys %cpi_vars::FORM ), "\n"
	if( %cpi_vars::FORM );

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
#	Update a record if there is new information.			#
#########################################################################
sub update_record
    {
    my( $tbl, $ind ) = @_;
    &DBwrite();
    &DBadd( $tbl, $ind );
    print STDERR "update_record($tbl,$ind)\n";
    &DBpop();
    }

#########################################################################
#	Create a unique key, but leave some clues as to what type of	#
#	table it goes to.						#
#########################################################################
sub new_tagged_key
    {
    my( $tbl ) = @_;
    my $ret = substr($tbl,0,1) . "_" . &DBnewkey();
    #&xprint( "Creating new $tbl key:  $ret<br>\n" );
    my $checkname = &DBget($ret,"Name");
    &autopsy(
	"new_tagged_key($tbl) created $ret which already exists ($checkname)")
	if( $checkname );
    return $ret;
    }

#########################################################################
#	Generate a quasi-difficult to guess id.  Could be much more	#
#	difficult.  No requirement for it to be unique.			#
#########################################################################
sub secret_id
    {
    return &cpi_compress_integer::compress_integer($NOW);
    }

#########################################################################
#	Takes either an html file or html text, uses an external	#
#	utility to convert it to pdf.  Basically no error checking.	#
#########################################################################
sub html_to_pdf
    {
    my( $html_contents ) = @_;
    my $html_file;
    my @to_remove;
    if( $html_contents !~ /</ )		# Nobody will embed a < in a filename
        { $html_file = $html_contents; }
    else
	{
	$html_file = &tempfile(".html");
	&write_file( $html_file, $html_contents );
	}
    my $ret = &read_file(
	"$WKHTMLTOPDF --print-media-type $html_file - 2>/dev/null |" );
    }

#########################################################################
#	Convert a number from a base 
#########################################################################
my @dig_list;		# Set in decode_progress
my %dig_map;
my $dig_radix;
sub convert_base
    {
    my ( @digs ) = split(//,$_[0]);
    my $n = 0;
    my $d;
    #print "dig_list=[",join(",",@dig_list),"]<br>\n";
    while( defined($d = shift(@digs)) )
	{
	#print "d($d) maps to [",$dig_map{$d},"].<br>\n";
	$n = $n*$dig_radix + $dig_map{$d};
	}
    #print "convert_base($_[0]) returns [$res]<br>\n";
    return $n;
    }

#########################################################################
#	Figure out what directories need to be made to create file.	#
#	If you have the contents, go ahead and just do it.		#
#########################################################################
sub setup_file
    {
    my ( $outarg, @contents ) = @_;
    my( $openfnc, $fn ) =
        ( $outarg=~/^([>]+)\s*(.*?)$/
	? ( $1, $2 )
	: ( ">", $outarg ) );
    my( @pieces ) = split(/\//,$fn);
    pop( @pieces );
    push( @pieces, "." ) if( ! @pieces );
    my $dirname = join("/",@pieces);
    #return undef if( ! -d $dirname && ! system("mkdir -p '$dirname'") );
    #system("mkdir -p '$dirname'") if( ! -d $dirname );
    &mkdirp( 0775, $dirname ) if( ! -d $dirname );
    open( OUT, "$openfnc $fn" ) 
        || &autopsy("Cannot $openfnc to ${fn}:  $!");
    binmode OUT;		# Avoid "Wide character in print" error messages
    if( @contents )
        {
	print OUT @contents;
	close( OUT );
	}
    return $fn;
    }

#########################################################################
#	Check if administrator wants updating windows to stop.		#
#########################################################################
sub stop_updates_if_needed
    {
    if( my $reason = &read_file($EXIT_FILE,"") )
	{
	$reason =~ s/\n/\\n/g;
	print "<script>\nalert('$reason');\nparent.window.close();\n</script>\n";
	&cleanup( 0 );
	}
    }

#########################################################################
#	We're not a web program.  Triage!				#
#########################################################################
sub non_CGI_handler
    {
    my @problems;
    if( ! defined($ARGV[0]) )
	{ push(@problems,"No arguments specified."); }
    elsif( $ARGV[0] eq "route" )	{ &do_one_route( @ARGV[1..3] );	}
    elsif( $ARGV[0] eq "reindex" )	{ reindex( $ARGV[1] );		}
    elsif( $ARGV[0] eq "print" )	{ dump_indices();		}
    elsif( $ARGV[0] eq "sanity" )	{ sanity();			}
    elsif( $ARGV[0] eq "trip" )		{ &trip_update();		}
    elsif( $ARGV[0] eq "pomap" )	{ &pomap( @ARGV[1..$#ARGV] );	}
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
	    if( -r $info_file )
		{
		my %info;
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
		if( -r $fname )
		    {
		    my $modified = &file_modified($fname);
		    push( @toprint,
			"<select onChange='",
			"if(this.value==\"doc_send\"){do_submit(\"func\",this.value,\"what\",\"$base.$ftype\",\"destination\",prompt(\"Send unsigned file to what address\"));} else if(this.value!=\"doc_del\"||confirm(\"XL(Are you sure you want to delete $ftype) $base?\")){do_submit(\"func\",this.value,\"what\",\"$base.$ftype\");}this.selectedIndex=0;'>",
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
			"<select name=digital_signature QonChange='",
			( $base eq $NEW_DOCUMENT
			    ? "(ebid(\"new_contents_id\")).click();"
			    : "do_submit(\"func\",\"doc_sign\",\"what\",\"$base\");" ),
			"'>",
			"<option disabled selected>",
			( $base eq $NEW_DOCUMENT
			    ? "XL(Upload and sign with key)"
			    : "XL(Sign with key)" ),
			"</option>" );
		    foreach my $sigbase ( &files_in( "$KEYS/$cpi_vars::USER", ".*\\.private\\.asc" ) )
			{
			push( @toprint,
				"<option value='$sigbase'>",
				&filename_to_text($sigbase),
				"</option>\n" );
			}
		    push( @toprint, "</select>" );
		    if( 1 || $ENV{HTTP_USER_AGENT}=~/Safari/
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
    my $doc_as_jpg_b64 = &read_file("$CVT '$unsigned' -.jpeg|tee /usr/local/projects/sign/debug/foo.jpg |base64 -w 0 |");

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

    &write_file( $unsigned, $cpi_vars::FORM{new_contents} );
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
    my $digital_file		= "$KEYS/$cpi_vars::USER/$cpi_vars::FORM{digital_signature}";
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

    my %info =
	(
	name			=> $name,
	user			=> $cpi_vars::USER." ("
				.	&dbget($cpi_vars::ACCOUNTDB,
					"users",$cpi_vars::USER,"fullname")
				. ")",
	signed			=> $NOW,
	digital_signature	=> $cpi_vars::FORM{digital_signature},
	size			=> -s $signed,
	agent			=> $ENV{HTTP_USER_AGENT},
	remote_addr		=> $ENV{REMOTE_ADDR},
	analog_location		=> join(",",$colpct,$rowpct),
	cookie			=> $cookie
	);
    &write_file( $info_file,
	Data::Dumper->Dump( [ \%info ], [ qw(*info) ] ) );
    push( @msgs, "$unsigned uploaded");
    &func_docs_show(@msgs);
    }

#########################################################################
#	Dump an info file.						#
#########################################################################
sub info_table
    {
    my( $base_file ) = @_;
    my %info;
    my @toprint = ( &app_top(), "<table style='border-collapse:collapse'>" );
    my $info_file = $base_file;
    $info_file =~ s/\.(unsigned|signed)\.*/.info.po/g;
    if( ! -r $info_file )
        {
	push( @toprint,
	    "<tr><th valign=top align=left>XL(Document name):</th>",
		"<td>$base_file</td></tr>",
	    "<tr><th valign=top align=left>XL(Uploaded):</th>",
	        "<td>",&file_modified($base_file),"</td></tr>" );
	}
    else
	{
	eval( &read_file( $info_file ) );
	push( @toprint,
	    "<input type=hidden name=c value='",$info{cookie},"'>",
	    "<tr><th valign=top align=left>XL(Document name):</th>",
		"<td valign=top>",$info{name},"</td></tr><tr>",
		"<th valign=top align=left>XL(Signing user):</th>",
		"<td valign=top>",$info{user},"</td></tr><tr>",
		"<th valign=top align=left>XL(Signed):</th>",
		"<td valign=top>", &time_string($YMDHM,$info{signed}), "</td></tr><tr>",
    #	    "<th valign=top align=left>XL(Location on document):</th>",
    #	    "<td valign=top>",$info{analog_location},"</td></tr><tr>",
		"<th valign=top align=left>XL(Digital signature):</th>",
		"<td valign=top>",&filename_to_text($info{digital_signature}),"</td></tr><tr>",
		"<th valign=top align=left>XL(Agent):</th>",
		"<td valign=top>",$info{agent},"</td></tr><tr>",
		"<th valign=top align=left>XL(Agent IP):</th>",
		"<td valign=top>",$info{remote_addr},"</td></tr><tr>",
		"<th valign=top align=left>XL(Size in bytes):</th>",
		"<td valign=top>",$info{size},"</td></tr><tr>",
		"<th valign=top colspan=2><input type=button",
		    " onClick='do_submit(\"func\",\"doc_viewanon\");'",
		    " value='XL(View signed document)'></th></tr>\n" );
	}
    push( @toprint, "</table></form>" );
    &xprint( @toprint );
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
    my $to_view = join("/",$DOCUMENTS,$relative_file.".pdf");
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
    &info_table("$DOCUMENTS/$relative_file");
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
    my @tbl = ( "<html><body><table style='border-collapse:collapse'>" );
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
	push( @tbl,
	    "<tr><th valign=top align=left>XL(Document name):</th>",
		"<td valign=top>",$info{name},"</td></tr><tr>",
		"<th valign=top align=left>XL(Signing user):</th>",
		"<td valign=top>",$info{user},"</td></tr><tr>",
		"<th valign=top align=left>XL(Signed):</th>",
		"<td valign=top>", &time_string($YMDHM,$info{signed}), "</td></tr><tr>",
    #	    "<th valign=top align=left>XL(Location on document):</th>",
    #	    "<td valign=top>",$info{analog_location},"</td></tr><tr>",
		"<th valign=top align=left>XL(Digital signature):</th>",
		"<td valign=top>",&filename_to_text($info{digital_signature}),"</td></tr><tr>",
		"<th valign=top align=left>XL(Agent):</th>",
		"<td valign=top>",$info{agent},"</td></tr><tr>",
		"<th valign=top align=left>XL(Agent IP):</th>",
		"<td valign=top>",$info{remote_addr},"</td></tr><tr>",
		"<th valign=top align=left>XL(Size in bytes):</th>",
		"<td valign=top>",$info{size},"</td></tr>" );
        push( @msgs, "Signed '$info{name}' sent to $cpi_vars::FORM{destination}" );
	}
    else
        {
	push( @tbl,
	    "<tr><th valign=top align=left>XL(Document name):</th>",
	        "<td valign=top>",$base_file,"</td></tr>",
	    "<tr><th valign=top align=left>XL(Uploaded):</th>",
	        "<td valign=top>",&file_modified($to_send),"</td></tr>" );
	push( @subject, "uploaded", $to_send,
	    &time_string( $YMDHM, &file_modified($to_send) ) );
        push( @msgs, "$to_send sent to $cpi_vars::FORM{destination}" );
	}
    push( @tbl, "</table></body></html>" );
    &sendmail( $cpi_vars::DAEMON_EMAIL,
	$cpi_vars::FORM{destination},
	join(" ",@subject),
	&xlate(join("\n",@tbl)),
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
    my( $name ) = $cpi_vars::FORM{new_name};
    my $directory = "$KEYS/$cpi_vars::USER";
    &mkdirp( $directory );
    my $basefile = "$directory/".&text_to_filename($name);
    my @msgs;

    my $tempname = "$basefile.$$";	# Do not use tempfile as it
    					# could leave file on a different
					# filesystem which would cause
					# subsequent rename() to fail.
    &write_file( $tempname, $cpi_vars::FORM{new_contents} );
    my $contents_type = &read_file( "file - < '$tempname' |" );
    if( $contents_type !~ /PGP (.*) key/ || ! &inlist($1,@KEY_TYPES) )
        { push( @msgs, "Cannot identify file contents." ); }
    else
	{
	my $new_name = "$basefile.$1.asc";
	if( rename( $tempname, $new_name ) )
	    { push( @msgs, "$new_name uploaded." ); }
	else
	    { push( @msgs, "Rename to $new_name failed, left as ${tempname}:  $!" ); }
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
