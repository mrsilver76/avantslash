#!/usr/bin/perl

############################################################################
# AvantSlash
my $version = "4.17";
# Copyright (c) Richard Lawrence and Han-Kwang Nienhuys 2000-2025
############################################################################
#
# This program is free software; you can redistribute it and/or modify   
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or 
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,  
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License      
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307 USA
#
############################################################################
# For instructions please read the file called README.
# Settings should be changed within the file "config.local", using
# "config.dist" as an example.
#
# If the configuration and cache are not in the current directory,
# then delete the next line, remove the # from the line after it and
# set $path accordingly.

my $path = ""; # default: empty string
# my $path = "/home/richard/public_html/avantslash/";


#
# You should not need to change anything below this line.
############################################################################

use strict;
use CGI::Carp qw(fatalsToBrowser);
use POSIX;
use LWP;
use CGI qw(:param);
use URI::Escape;
use Cwd;


# Change directory

if ($path ne "") {
    chdir($path) || die("Path '$path': $!");
}

# In case of any problems

$SIG{ALRM} = sub { exit };
alarm(35);

use constant ONE_MINUTE => 60;

my $self_url = $ENV{'SCRIPT_NAME'};
my $clean_html = "";
my $clean_done = 0;
my $thisyear = 1900 + (localtime(time))[5];
my $page = ""; # raw slashdot HTML code
my @missing_vars; # variables missing in configuration
my %fetch_info = qw(url undef
                    cache undef
                    pagedate 0
                    statuscode undef
                   );

# special categories of cache lifetime (in units of 1 minute)
my %cache_life_min = ("ckupdate", 7*24*60,
		      "ajax", 120,
		      "issue", 180,
		      "search", 180,
		      "css", 24*60,
		      "democalls", 8*60,
		      "bookmarks", 60*24*365, # 1 year
    );
    

# Global variables
my $first_js = 1; # static variable for javascript output

my %timeouts = ("slashdot", 30, "avantslash", 8); # in seconds

# %prefs uses same keys as configuration file, but obligatory lowercase
my %prefs = qw(soylent 0
               compressed_characters 100
	       threshold 4
	       mp_show_posted_by 1
	       mp_show_department 1
	       mp_show_blurb 1
	       mp_show_read_more 1
	       mp_show_poll 1
               mp_max_stories 99
	       ap_show_posted_by 1
	       ap_show_department 1
	       ap_show_story 1
	       ap_threshold_options 1
	       max_comments 0
	       no_compressed_comments 0
               extra_links 0 
	       default_stylesheet mini_slashdot
               timezone auto
               time_fmt %F_%H:%M
	       cache_timeout 30
	       debugging 0
	       dump_reformatted_html 0
	       enable_local_cache 1
               check_updates 1
               demo_mode 0
	       );

my $as_user_agent = "Mozilla/5.0 (Linux; rv:53.0) Gecko/53.0 Firefox/53.0)";

# override settings in demo mode (also demo_mode!)
my %demo_settings = qw(
    cache_timeout 360
    max_comments 20
    mp_max_stories 10
    demo_mode 1
    enable_local_cache 1
);

# these preferences can take non-numeric or negative values
my %prefs_non_numeric = qw(default_stylesheet 1 timezone 1 time_fmt 1);

# these url parameters are allowed in demo mode (regexp)
my $demo_cgi_whitelist = "ajax|base|ckupdate|comments|css|issue|setcss|showcredits|showprefs|style|threshold|ua|referer|xlinks|force_reload|return";

# Load in config file
@missing_vars = set_configuration();

# Process CGI parameters and proceed
process_cgi_params();

exit;


# sanitize and process CGI parameters
# argument: ref to sanitized parameter hash
sub process_cgi_params {
    # check abuse in demo mode
    $prefs{'demo_mode'} && demo_sanity_check();
    
    # Allow people to override debugging values
    if (cgi_param("debug")) {
	$prefs{"debugging"} = cgi_param("debug");
	$prefs{"debugging"} =~ s/[^0-9]/0/g;
    }
    if (cgi_param("xlinks")) {
	$prefs{"extra_links"} = cgi_param("xlinks");
    } 
    if ((my $issue = cgi_param("issue")) ne "") {
	# older front page, 0=today, 1=yesterday, etc.
	$issue =~ s/[^0-9]//g; 
	get_html(\$page, "issue", $issue);
	parse_main_page("issue");
	exit;
    }

    if ((my $issuedate = cgi_param("issuedate")) ne "") {
	# older front page, 0=today, 1=yesterday, etc.
	$issuedate =~ s/[^0-9]//g;
	(length($issuedate) != 8) && fatal_error("Issue date '".cgi_param("issuedate")."' is not 8 digits.\n");
	($issuedate < 19950101 || $issuedate > POSIX::strftime("%Y%m%d", gmtime()))  &&
	    fatal_error("Issue date $issuedate out of range.\n");
	get_html(\$page, "issuedate", $issuedate);
	parse_main_page("issue");
	exit;
    }

    if (cgi_param("showcredits") eq "1") {
	show_credits(@missing_vars);
	exit;
    }

    if (cgi_param("showprefs") eq "1") {
	show_prefs(@missing_vars);
	exit;
    }

    if (cgi_param("upgrade") ne "") {
	run_upgrade(cgi_param("upgrade"))
    }

    # check threshold for comments
    my $new_threshold = cgi_param("threshold");
    if ($new_threshold ne "") {
	$prefs{"threshold"} = $new_threshold;
    }

    if ((my $comments = cgi_param("comments")) ne "") {
	# article/poll:  comments
	# should be something like /13/12/29/0416259 or poll/1234/
	$comments =~ s![^\d/,pol]!!g; 
	$comments = sanitize_string_withslash($comments);
	get_html(\$page, "comments", $comments);
	parse_comments();
    } elsif ((my $ajax = cgi_param("ajax")) ne "") {
	# article / comments
	$ajax = sanitize_string_withslash($ajax);
	get_html(\$page, "ajax", $ajax);
	parse_ajax_comment($ajax);
    } elsif ((my $ckupdate = cgi_param("ckupdate")) ne "") {
	# check for updates
	$ckupdate = ($ckupdate ne "2") ? 1 : 2; # 1=page, 2=generate js
	($ckupdate == 1) && purge_cache("ckupdate-*", 30); # force re-check
	get_html(\$page, "ckupdate", "z");
	parse_ckupdate($ckupdate);
    } elsif ((my $css = cgi_param("css")) ne "") {
	$css = sanitize_string_noslash($css);
	generate_css($css);
    } elsif ((my $search = cgi_param("search")) ne "") {
	$search =~ s![^ a-zA-Z0-9]!!g; 
	get_html(\$page, "search", $search);
	parse_main_page("search", $search);
    } elsif ((my $rss = cgi_param("rss")) ne "") {
	$rss = 1;
	get_html(\$page, "rss", 0);
	parse_rss();
    } elsif (cgi_param("setcss") ne "") {
	set_css_cookie();
    } elsif (cgi_param("bookmark") ne "") {
	set_bookmark();
    } elsif (cgi_param("delbm") ne "") {
	del_bookmark();
    } elsif (cgi_param("showbm") ne "") {
	show_bookmarks();
    } elsif ($prefs{'demo_mode'}) {
	# demo mode and nothing else: main page 3 days ago
	get_html(\$page, "issue", 3);
	parse_main_page("issue"); 
    } else {
	get_html(\$page, "main", "");
	parse_main_page("main");
    }
    
    exit;
}


# parse the RSS page
sub parse_rss {
    print("Content-Type: application/rss+xml\n\n");
    
    # cleanup facebook/twitter/doubleclick stuff
    $page =~ s/AVANTSLASH_URL=.*$//s;
    my $remove_hrefs = join("|",
			    "twitter.com/home",
			    "feedads.",
			    "www.facebook.com/sharer");
    $page =~ s!\&lt;a href=\"http://($remove_hrefs).*?\&lt;/a\&gt;!!g;
    $page =~ s!\&lt;p\&gt;(\&lt;br/\&gt;)?\s*\&lt;/p\&gt!!gs;
    $page =~ s!<image rdf:resource.*?/>!!g;
    $page =~ s!<image [^>]*>.*?</image>!!gs;
    $page =~ s!<link>.*?</link>!!g;
    $page =~ s!&lt;iframe.*?&lt;/iframe&gt;!!g;
    $page =~ s!&lt;img.*?(&lt;/img|/)&gt;!!g;
    $page =~ s!(&lt;/a&gt;) at Slashdot!$1 in AvantSlash!g;
    $page =~ s!<feedburner:origLink>.*?</feedburner:origLink>!!g;

    repoint_urls(\$page);
    print $page;
}

# parse the main page
# uses global $page varibale for html code
# argument: 'search' (+search string) or 'main'

sub parse_main_page
{
    return $prefs{soylent} ? parse_main_page_soylent(@_) : parse_main_page_slashdot(@_);
}

sub parse_main_page_soylent
{
  my $mptype = shift;
  my $search;
  if ($mptype eq "search") {
      $search = shift;
      show_header("$search - Soylent search");
  } elsif ($mptype eq "issue")  {
      show_header("Avantslash: older issue");
  } else {
      show_header("Avantslash: Soylent is People");
  }
  
  if ($#missing_vars >= 0)
  {
    print "<p><div class=\"error\">\n".
	"Some configuration settings are missing which may affect your reading experience\n".
	"[<a href=\"$self_url?showcredits=1\">more</a>]</div></p>";
  }

  if ($mptype eq "search") {
      print("<div class='searchheader'>\n".
	    "Searched for '$search'.<br>\n".
	    search_form($search).
	    "</div>");
  }
  
  my ($title, $blurb, $posted, $dept, $more, $hiddenstory, $ncomments);
  $title = $dept = $more = $posted = $blurb = $ncomments = "???";
  $hiddenstory = "";
  my $poll_story = "";
  my $storycount = 0;
  
  my @bits = split(/\n/, $page);
  foreach (@bits)
  {
    # first, watch out for the small stories with no blurb
    if ($prefs{"debugging"} >= 2) { dumpline(); }
  
    # title
    if (m!<div class=\"title\b.*<h3[^>]*>(.*?)</h3>!)
    {
      $title = remove_tags_except_basic($1);
      
      # Strip all HTML tags from the line
      $title =~ s/<.+?>//g;
  
      debug_msg("title", $title) if ($prefs{"debugging"});
    }
    # search result
    elsif (m!<div class=\"search-results\">.*?<a href=\".*?sid=([\d/]+)\">(.+?)</a>!) {
	$more = $1;
	$title = $2;
	if ($prefs{"debugging"}) {
	    debug_msg("title", $title);
	    debug_msg("more", $more);
	}
	$posted="";
	if ($more =~ m!^(\d\d)/(..)/(..)/!) {
	    $posted = "Posted on 20$1-$2-$3.";
	}
	$dept="";
	
    }

    # or poll
    if ($prefs{"mp_show_poll"} && m!<div [^>]*id=\"poll-content\">(.*?)</form>!s) {
	my $x = $1;
	if ($x =~ m!<input[^>]+\"mainpage\">\s*<p><b>(.*?)</b>!) {
	    $title = "Poll: ".remove_tags($1);
	}
	my $qid = "??";
	if ($x =~ m!<a href=[^>]+/pollBooth.pl\?qid=([0-9]+)!) {
	    $qid = $1;
	    $more="poll/$1";
	}
	($x =~ m!Comments:<b>([0-9]+)!) && ($ncomments = $1);
	$blurb = "";
	while ($x =~ s!<input type=\"radio\"[^>]*>(.*?)</li>!!) {
	    if ($blurb ne "") { $blurb .= " / "; }
	    $blurb .= "$1";
	}
	$blurb .= "&nbsp; [<a href=\"https://soylentnews.org/pollBooth.pl?qid=$qid\">cast your vote</a>]";
	$posted = $dept = "";
	$hiddenstory = " hiddenstory";
	
	if ($prefs{"debugging"}) {
	    debug_msg("title", $title);
	    debug_msg("blurb", $blurb);
	    debug_msg("qid", $qid);
	    debug_msg("ncomments", $ncomments);
	}
    }
    # posted
  
    elsif (m!<div class="details"[^>]*>(.+?)<br>(.+?)</div>!)
    {
      $posted = remove_tags($1);
      $dept = remove_tags($2);
       
      # Remove any links in the line
      $posted =~ s/<a href.+?>(.+?)<\/a>/$1/gi; 
      $posted =~ s/<.+?>//g;
  
      # Remove any links in the line
      $dept =~ s/<a href.+?>(.+?)<\/a>/$1/gi; 
      $dept =~ s/<.+?>//g;
      
      debug_msg("posted", $posted) if ($prefs{"debugging"});
      debug_msg("department", $dept) if ($prefs{"debugging"});
    }
  
    # the blurb
  
    elsif (m!<div class=\"intro\">(.*?)</div>!)
    {
      $blurb = remove_tags_except_basic($1);
      $blurb =~ s!<a [^>]+>original submission</a>!!i;
      if ($prefs{"debugging"}) {
	  debug_msg("blurb", $blurb);
	  debug_msg("hiddenstory", $hiddenstory);
      }
    }
  
    # link to more
  
    elsif (m!<li class=.more.> <a [^>]*href=\"([^\"]+)\".*>([0-9]+)</a> comments!)
    {
        # full href is e.g "//soylentnews.org/articles/14/02/23/056215.shtml"
	# or //soylentnews.org/article.pl?sid=14/02/27/2036233
        $more = $1;
	$ncomments = $2;
	my $more_raw = $more;
        $more =~ s!^.*(articles/|article.pl\?sid=)(\d+/\d+/\d+/\d+)\b.*$!$2!;

	if ($prefs{"debugging"}) {
	    debug_msg("more-raw", $more_raw);
	    debug_msg("more", $more);
	    debug_msg("ncomments", $ncomments);
	}
    }
  
      # display once the last item ($more) is found. This reduces the impact if
      # slashdot changes only for one of the items.

    if ($more && $more ne "???" && $blurb && $blurb ne "???")
    {
      debug_msg("Got everything...") if ($prefs{"debugging"});
  
      # clean up any missing blockquotes and repoint external links
      cleanup_message(\$blurb);

      my $item = "<div class=\"item$hiddenstory\">\n".
	  "<h2><a href=\"$self_url?comments=$more\">$title</a></h2>\n";
      if ($prefs{"mp_show_posted_by"} || $prefs{"mp_show_department"}) {	
	  $item .=  "<div class=\"subtitle\">\n";
	  if ($prefs{"mp_show_posted_by"}) {
	      $posted =~ s!( on )(.*[AP]M)!$1.reformat_time($2)!e;
	      $item .=  "$posted\n";
	  }
	  $item .= "<div>$dept</div>\n" if ($prefs{"mp_show_department"});
	  $item .= "</div>\n";
      }
      $item .= "$blurb\n" if ($prefs{"mp_show_blurb"});
      my $cmt_anchor = ($mptype eq "search") ?
	  "(Read more)" : "($ncomments comments)";
      $item .= "<p><a href=\"$self_url?comments=$more\">$cmt_anchor</a></p>\n" if ($prefs{"mp_show_read_more"});
      $item .= "</div>\n\n";
      if ($title =~ /^Poll/) {
	  $poll_story = $item;
      } else {
	  print($item);
      }
      
  
      $title = $dept = $more = $posted = $blurb = "???";
      $hiddenstory = "";
      ++$storycount;
      if ($storycount >= $prefs{'mp_max_stories'}) {
	  print("<p>(Showed only first $storycount stories.)\n");
	  last;
      }
    }
  }

  if ($prefs{"mp_show_poll"}) {
      print($poll_story);
  }

  
  status_message(1);

  print_ckupdate_js();
  # need to see at least poll plus one other story
  if ($storycount < 2 && $mptype ne "search") {
      print_ckupdate_link("SoylentNews main page");
  }
  show_footer(1, "<br>".search_form($search));
}


sub parse_main_page_slashdot
{
  my $mptype = shift;
  my $search;
  if ($mptype eq "search") {
      $search = shift;
      show_header("$search - Slashdot search");
  } elsif ($mptype eq "issue")  {
      show_header("Avantslash: older issue");
  } else {
      show_header("Avantslash: News for nerds, stuff that matters");
  }

  
  if ($#missing_vars >= 0)
  {
    print "<p><div class=\"error\">\n".
	"Some configuration settings are missing which may affect your reading experience\n".
	"[<a href=\"$self_url?showcredits=1\">more</a>]</div></p>";
  }

  if ($mptype eq "search") {
      print("<div class='searchheader'>\n".
	    "Searched Slashdot for '$search'.<br>\n".
	    search_form($search).
	    "</div>");
  }
  
  my ($title, $story_link,
      $blurb, $posted, $dept, $more, $hiddenstory, $ncomments);
  $title = $dept = $more = $posted = $blurb = $ncomments = "???";
  $hiddenstory = $story_link = "";
  my $storycount = 0;
  
  my @bits = split(/\n/, $page);
  foreach (@bits)
  {
    # first, watch out for the small stories with no blurb
    if ($prefs{"debugging"} >= 2) { dumpline(); }
  
    if (m!<div class="briefarticle".+?> ?<span class="section">(.+?)</span> ?<span class="storytitle"><a href=".+?sid=(\d\d/\d\d/\d\d/\d{5,7})">(.+?)</a> ?</span>!)
    {
      my $smsection = $1;
      my $smmore = $2;
      my $smtitle = $3;
  
      # Remove any tags which may or may not be there
      $smtitle =~ s/<.+?>//g;
      $smsection =~ s/<.+?>//g;
  
      print "<p><b>$smsection</b> <a href=\"$self_url?comments=$smmore\">$smtitle</a></p>";
    }
  
    # title & link to story page

  if (m!<article.*?>.*?<span id=\"title-[^>]*> <a [^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a!)
    {
      my $more_raw = remove_tags_except_basic($1);
      $title = remove_tags_except_basic($2);
      if (m!<a class="story-sourcelnk" href="(.*?)".*?>(.*?)</a!) {
	  $story_link = 
	      "\n<div class='storylink'>[Story at <a href='$1'>$2</a>]</div>";
	  if ($prefs{'debugging'}) {
	      debug_msg("story_link", "$2 --> $1");
	  }
	  
	  $story_link =~ s![\(\)]!!g;
	  
      }
      $title =~ s/<.+?>//g; 
      $more = $more_raw;
      $more =~ s!^.*/story/([0-9]+/[0-9]+/[0-9]+/[0-9]+)/.*$!$1!;

      if (m!<span class=\"comments[^>]*>([0-9]+)</span>!) {
	  $ncomments = $1;
      }

      if ($prefs{'debugging'}) {
	  debug_msg("title", $title);
	  debug_msg("more-raw", $more);
	  debug_msg("more", $more);
	  debug_msg("ncomments", $ncomments);
      }
      
    }

    # or poll
    if ($prefs{"mp_show_poll"} && m!<form id="pollBooth"!) {
	if (m!<h3>(.*?)</h3>!) {
	    $title = "Poll: ".remove_tags($1);
        }

	$blurb = "";
	    
	my $x = $_;
	while ($x =~ s!<input type=\"radio\"[^>]+>(.*?)</label>!!) {
	    if ($blurb ne "") { $blurb .= " / "; }
	    $blurb .= remove_tags($1);
	}
	$posted = $dept = "";
	if ($x =~ m!<input type="hidden".*?value="(\d+)">!) {
	    $more = "poll/$1/";
	    $blurb .= "<p><a href=\"https://slashdot.org/pollBooth.pl?qid=$1\">[Your vote]</a>"
	}
	if ($prefs{"debugging"}) {
	    debug_msg("title", $title);
	    debug_msg("blurb", $blurb);
	    debug_msg("more", $more);
	}
    }
    # posted
  
    elsif (m!<span class="story-byline">(.*Posted by.*)</time>.*?(from the .* dept.)!) {
      $posted = remove_tags($1);
      $dept = remove_tags($2);
       
      # Remove any links in the line
      $posted =~ s/<a href.+?>(.+?)<\/a>/$1/gi; 
      $posted =~ s/<.+?>//g;
  
      # Remove any links in the line
      $dept =~ s/<a href.+?>(.+?)<\/a>/$1/gi; 
      $dept =~ s/<.+?>//g;
      
      debug_msg("posted", $posted) if ($prefs{"debugging"});
      debug_msg("department", $dept) if ($prefs{"debugging"});
    }
  
    # the blurb
  
    elsif (m!<div class=\"(body|hide)\"[^>]*>.*?<div id=\"text-[^>]+>(.+?)</div>!)
    {
      $blurb = remove_tags_except_basic($2);
      $hiddenstory = ($1 eq "hide" && $mptype ne "search") ? " hiddenstory" : "";
      if ($prefs{"debugging"}) {
	  debug_msg("blurb", $blurb);
	  debug_msg("hiddenstory", $hiddenstory);
      }
    }

    # the blurb for video (not video bytes)

    elsif (m!<div class="video-thumb">.*?</div>(.*?)</div>!)
    {
      $blurb = remove_tags_except_basic($1);
      if ($prefs{"debugging"}) {
	  debug_msg("blurb", $blurb);
	  debug_msg("hiddenstory", $hiddenstory);
      }
    }
    
  
  
      # display once the last item ($more) is found. This reduces the impact if
      # slashdot changes only for one of the items.      
  
    if ($blurb && $blurb ne "???")
    {
      debug_msg("Got everything...") if ($prefs{"debugging"});
  
      # remove the no ad tag
      $blurb =~ s/<P> <!-- no ad \d+ -->//gi;
  
      # clean up any missing blockquotes and repoint external links
      cleanup_message(\$blurb);
  
      # remove trailing <P> in blurb that suddenly started appearing one day
      $blurb =~ s/\s<P>\s*$//i;
		print "<div class=\"item$hiddenstory\">\n".
	    "<h2><a href=\"$self_url?comments=$more\">$title</a></h2>\n";
      if ($prefs{"mp_show_posted_by"} || $prefs{"mp_show_department"}) {	
	  print("<div class=\"subtitle\">\n");
	  if ($prefs{"mp_show_posted_by"}) {
	      $posted =~ s!( on )(.*[AP]M)!$1.reformat_time($2)!e;
	      print("$posted\n");
	  }
	  print("<div>$dept</div>\n") if ($prefs{"mp_show_department"});
	  print("</div>\n");
      }
      print("$blurb\n") if ($prefs{"mp_show_blurb"});
      print("<br>$story_link\n".
	    "<a href=\"$self_url?comments=$more\">($ncomments comments)</a>\n") if ($prefs{"mp_show_read_more"});
      print("</div>\n\n");
  
      $title = $dept = $more = $posted = $blurb = "???";
      $story_link = $hiddenstory = "";
      ++$storycount;
      if ($storycount >= $prefs{'mp_max_stories'}) {
	  print("<p>(Showed only first $storycount stories.)\n");
	  last;
      }
    }
  }
  status_message(1);

  print_ckupdate_js();
  # need to see at least poll plus one other story
  ($storycount < 2) && print_ckupdate_link("Slashdot main page");
  show_footer(1, "<br>".search_form($search));
}


# parse comments
sub parse_comments
{
    return $prefs{soylent} ? parse_comments_soylent(@_) : parse_comments_slashdot(@_);
}

# parse comments
sub parse_comments_soylent
{
  my ($title, $story, $posted, $dept, $header);
  my ($i, $elements);
  my $thread_mode = 0;
  my $thereismore = 0;
  my $shownblurb = 0;
  my $thr_cid = "";
  my $thr_title = "";

  if (cgi_param("comments") =~ m!^\d+,(\d+)$!) {
      $thread_mode = 1;
      $thr_cid = $1;
  }

  
  # in debug mode, start with a standard header
  if ($prefs{debugging}) {
      show_header("AvantSlash comments debugging");
      $header = 1;
  }

  my @bits = split(/\n/, $page);
  $elements = scalar @bits;
  my $commentscount = 0;

  # comments page headers (soylent)
  for ($i = 0; $i < $elements; $i++)
  {
    $_ = $bits[$i];
    if ($prefs{"debugging"} >= 2) { dumpline(); }

    # Title for story/thread page
    if (!defined($title) && m!<div class=.title.*?<h3.*?>\s*(.*?)\s*</h3>!)
    {
	$title = remove_tags($1);
	$prefs{'debugging'} && debug_msg("title", $title);
	if ($thread_mode) {
	    $posted = "Showing comment thread. (<a href=\"$self_url?comments=$1\">original story</a>)";
	    $prefs{'debugging'} && debug_msg("posted", $posted);
	    $thr_title = "($title)";
	}	
    }

    # posted
    if (m!<div class=\"details[^>]*>(.+?)<br>(.+?)</div>!)
    {
	$posted = remove_tags($1);
	$dept = remove_tags($2);

	debug_msg("posted", $posted) if ($prefs{"debugging"});
	debug_msg("department", $dept) if ($prefs{"debugging"});
    }

    if (m!<div class=.intro\b!)
    {
      $story .= remove_tags_except_basic($_);

      # book reviews have more stuff
      if (m!<span class=\"bodytext\">(.*)</span>!) {
	  $story .= remove_tags_except_basic($1);
      }

      debug_msg("story", $story) if ($prefs{"debugging"});
    }

    # or poll results
    elsif (m!Displaying poll results!) {
	while (s!<caption class=\"barAnswer\">(.*?)</caption>.*?class=\"barPercent\">(\d+%)</td>!!) {
	    $story .= mk_pollbar((0+$2), remove_tags($1));
	}
	debug_msg("story", $story) if ($prefs{"debugging"});
    }

    # long stories: part 2
    elsif (m!<div class=\"full\">(.*)</div>!) {
	my $story2 = remove_tags_except_basic($1);
	if ($prefs{'debugging'}) { debug_msg('story_pt2', $story2); }
	$story .= $story2;
    }

    if (m!<div class=\"commentBoxForm\"!)  {
      debug_msg("Got everything...") if ($prefs{"debugging"});

      # Display the header if we haven't already

      if (!$header)
      {
        show_header($title);
        $header = 1;
	my $js = file_contents('expandmsg_soylent.js');
	print("\n<script type=\"text/javascript\">\n".$js."</script>\n");
      }

      # clean up blockquotes and repoint external links
      cleanup_message(\$story);

      print "<div class=\"item\">\n";
      print "<h2>$title</h2>\n";
      if ($thread_mode) {
	  print "<div class=\"subtitle\">\n";
	  print("Showing comment thread.");
	  print("</div>\n");
      } else {
	  print "<div class=\"subtitle\">\n";
	  if ($prefs{"ap_show_posted_by"}) {
	      $posted =~ s!( on )(.*[AP]M)!$1.reformat_time($2)!e;
	      print "$posted\n";
	  }
	  print "<div>$dept</div>\n" if ($prefs{"ap_show_department"});
	  print "</div>\n";
	  print "$story\n" if ($prefs{"ap_show_story"});
      }
      $shownblurb = 1;

      # bail out to the comments part
      last;
    }
  }

  (!$header) && show_header("Comments [could not parse title]");

  # Show the threshold change options

  if ($prefs{"ap_threshold_options"} && $shownblurb)
  {
    print "<div class=\"subtitle toppad\">\nShowing comments at threshold " . $prefs{"threshold"};
    if (!$prefs{"no_compressed_comments"} && $prefs{"compressed_characters"}) { 
	print " and summaries at " . ($prefs{"threshold"}-1);
    }
    print(".\n");
    my $urldata = cgi_param("comments");
    print("<form method='GET' action='$self_url'>\n".
	  "<input type=hidden name=comments value='$urldata'>\n".
	  "Change to: ".
	  "<select name='threshold'  onchange='this.form.submit()'>\n");
    foreach my $num (0..5) {
	my $selected = ($prefs{"threshold"} == $num) ? " selected" : "";
	print(" <option$selected value='$num'>&nbsp;$num&nbsp;</option>\n");
    }
    print "</select></form>\n</div>";
  }
  print("</div><!--item-->\n");


  ##### and now the comments (soylent) #####
  print("\n\n");
  my ($author, $score, $score_num, $message, $sid, $cid);
  my $j;
  my $uldepth = -1; # keep track of comment indentation
  my $current_title = "<blah>";
  $j=0;
  for (; $i < $elements; $i++)
  {
    $_ = $bits[$i];
    filterline();
    if ($prefs{"debugging"} >= 2) { dumpline(); }

    # keep track of UL indentation level
    my $n_ul_open = () = $_ =~ m!<ul!gi;
    my $n_ul_close = () = $_ =~ m!</ul!gi;
    if ($n_ul_open || $n_ul_close) {
	$uldepth += $n_ul_open - $n_ul_close;
	$prefs{"debugging"} && debug_msg("uldepth", $uldepth);
    }
    
    if (m!<div class=\"title\"> <h4><a.+?>(.+?)</a> <span id=\"comment_score_\d+?\" class=\"score\"> ?\(Score:(.*?)\).*</h4>!) 
    {
      $title = remove_tags($1);
      $score = remove_tags($2);
      $score_num = $score;
      $score_num =~ s!,.*$!!; # keep the numeric value only

      if ($prefs{"debugging"}) {
	  debug_msg("title", $title);
	  debug_msg("score", $score);
	  debug_msg("score_num", $score_num);
      }

    }
    #  <div class="details"> <><>by <><>NAME <>(12345)<><> ...
    elsif (m!<div class="details">!)
    {
	if (m!sid=([0-9]+)[^\"]+cid=([0-9]+)!) {
	    $sid = $1;
	    $cid = $2;
	    debug_msg("cid,sid", "$cid,$sid") if ($prefs{"debugging"});
	    if ($cid == $thr_cid) {
		$thr_title = "$title $thr_title";
	    }
	}
	s!<[^>]+>!!g; 
	s!([0-9][AP]M).*$!$1!g;
	s!writes:.*on !on !g;
	s!writes:!!g;
	$author = "Posted $_";
	debug_msg("author", $author) if ($prefs{"debugging"});
    }

    elsif (m!<div id=\"comment_body_\d+\">(.+)</div>!i)  {
      # Remove the "Read the rest of this comment" line and replace
      # with generic message
      $message = $1;
      $message =~ s!<div [^>]*class="sig">.*!!;
      $message = remove_tags_except_basic($message);

      my $msg_length = length(remove_tags($message));
      if ($prefs{"debugging"}) {
	  debug_msg("message", $message);
	  debug_msg("message-length", $msg_length);
      }

      # We have everything (i hope) so clean up message
      debug_msg("Got everything...") if ($prefs{"debugging"});
      ++$commentscount;

      cleanup_message(\$message);

      if ($j <= $prefs{"max_comments"}) {
	  my $msg_html = "";
	  
	  if ($score >= $prefs{"threshold"}) { 
	      # heuristics to decide whether to add a '[thread]' link
	      my $title_nore = $title;
	      $title_nore =~ s!^Re:\s*!!;
	      my $add_thread_link = $prefs{'extra_links'};
	      if ($title_nore ne "" && $title_nore ne $current_title) {
		  $add_thread_link = 1;
		  $current_title = $title_nore;
	      }
	      $msg_html .= format_msg($title, $score, $author, $message,
				      $msg_length, 1, $cid, $sid, $add_thread_link);
	  } elsif ($prefs{'no_compressed_comments'}==0 && $score == $prefs{'threshold'}-1) {
	      $msg_html .= format_msg_abbrev_soylent($title, $score, $author, $message,
						     $msg_length, $cid, $sid);
	  }

	  
	  if ($msg_html ne "") {
	      embed_div_inX($uldepth, \$msg_html);
	      print("$msg_html\n\n");
	      ++$j;
	  }
      } else {
	  if ($prefs{"debugging"} && $j > $prefs{"max_comments"}) {
	      debug_msg("Skipped due to $j > max_comments.\n");
	  }
	  elsif ($prefs{"debugging"} && $score_num < $prefs{"threshold"}-1) {
	      debug_msg("Skipped due to score $score_num < " . $prefs{"threshold"}-1);
	  }
	  elsif ($prefs{"debugging"}) {
	      debug_msg("Skipped.\n");
	  }
      }
      $author = $score = $author = $message = $cid = "";
    }
  } # for $i $elements
  if ($j == 0) {
      print "<p><small><b>There are no comments rated $prefs{threshold} or higher.</b></small></p>";
    } elsif ($j >= $prefs{"max_comments"})  {
      print "<p><small><b>Only the first " . $prefs{"max_comments"} . " comments are shown here.</b></small></p><hr>";
    }
  status_message(1);
  if ($thread_mode) {
      print_bookmark_link($thr_title);
  }
  my $extra_footer_html = "";
  if (!$prefs{'extra_links'}) {
      my $urldata = cgi_param("comments");
      $extra_footer_html =
	  "<a href=\"$self_url?comments=$urldata\&amp;threshold=$prefs{threshold}\&amp;xlinks=1\">".
	  "[Show extra thread/reply links]</a><br>";
  }
  print_ckupdate_js();
  (!$shownblurb || $commentscount == 0) && print_ckupdate_link("Soylentnews comments page");
  show_footer(0, $extra_footer_html);
}  


# parse comments
sub parse_comments_slashdot
{
  my $thread_mode = 0;
  my $is_poll = (cgi_param("comments") =~ m!poll!);
  my ($title, $story, $posted, $dept, $header, $story_link);
  my ($i, $elements);

  my $thereismore = 0;
  my $shownblurb = 0;
  my $poll_item = '';
  $story_link = "";
  my $thr_cid = "";
  my $thr_title = "";
  
  if (cgi_param("comments") =~ m!^\d+,(\d+)$!) {
      $thread_mode = 1;
      $thr_cid = $1;
  }

  # in debug mode, start with a standard header
  if ($prefs{debugging}) {
      show_header("AvantSlash comments debugging");
      $header = 1;
  }

  my @bits = split(/\n/, $page);
  $elements = scalar @bits;
  my $commentscount = 0;

  for ($i = 0; $i < $elements; $i++)
  {
    $_ = $bits[$i];
    if ($prefs{"debugging"} >= 2) { dumpline(); }

    # Title [1] for story/thread page
    if (m!<div class=\"title\b.*?<a href.*?/story/(\d+/\d+/\d+/\d+)/.*?>(.*?)</a>!)
    {
	$title = remove_tags($2);
	$prefs{'debugging'} && debug_msg("title1", $title);
	if ($thread_mode) {
	    $posted = "Showing comment thread. (<a href=\"$self_url?comments=$1\">original story</a>)";
	    $prefs{'debugging'} && debug_msg("posted", $posted);
	}
	$thr_title = "($title)";
    }

    # title for poll
    elsif ($is_poll && m!<h1>(.*?)</h1>!) {
	$title = "Poll: ".remove_tags($1);
	debug_msg("title", $title) if ($prefs{"debugging"});
	$posted = $dept = "";
    }

    elsif (m!<a class="story-sourcelnk" href="(.*?)".*?>(.*?)</a!) {
	$story_link = 
	    "\n<div class='storylink'>[Story at <a href='$1'>$2</a>]</div>";
	debug_msg('story_link', "$2 --> $1") if ($prefs{'debugging'});
	$story_link =~ s![\(\)]!!g;
    }

    if (m!<span class="story-byline">(.*)(from the .* dept\.)!) {
	$posted = remove_tags($1);
	$dept = remove_tags($2);
	debug_msg("posted", $posted) if ($prefs{"debugging"});
	debug_msg("department", $dept) if ($prefs{"debugging"});
    }
    # the story

    if (s!<(div|p)\s+id=\"text-[^>]*>(.+?)(</p> </div>|</div>)!!)
    {
      # Sometimes the Slashdot HTML stupidly uses "intro" twice and
      # so if you don't take into account that then you end up 
      # overwriting the contents of the previous one (sigh)
      # <p>...</p> is for slashdot beta 2013

      $story .= remove_tags_except_basic($2);
      # book reviews have more stuff
      if (m!<span class=\"bodytext\">(.*)</span>!) {
	  $story .= remove_tags_except_basic($1);
      }

      if (m!<h4 class=\"gravatar\"> <span.*?>(.+?)</span>!) {
	  # in 'slashdot beta 2013'...
	  $dept = remove_tags($1);
	  $prefs{'debugging'} && debug_msg("dept", $dept);
      }
      debug_msg("story", $story) if ($prefs{"debugging"});
    }

    if (m!<div\s+id="sdtranscript">(.+?)</div>!) {
	my $stran = remove_tags_except_basic($1);
	debug_msg("transcript", $stran) if ($prefs{'debugging'});
	$story .= $stran;
    }

    # or poll results
    elsif ($is_poll && m!<div class="poll-bar-label">(.*?)</div>!) {
	$poll_item = remove_tags($1);
	debug_msg("story", $story) if ($prefs{"debugging"});
    }
    elsif ($is_poll && m!<div class="poll-bar-text">.* (\d+%)</div>!) {
	my $percent = 0+$1;
	$story .= mk_pollbar($percent, $poll_item);
    }

    if (m!<div id=\"commentControlBoxStatus\"! ||
	m!<div class=\"ui-comment-form\">! )
    {
      debug_msg("Got everything...") if ($prefs{"debugging"});

      # Display the header if we haven't already

      if (!$header)
      {
        show_header($title);
        $header = 1;
      }

      # clean up blockquotes and repoint external links
      cleanup_message(\$story);

      print "<div class=\"item\">\n";
      print "<h2>$title</h2>\n";
      print "<div class=\"subtitle\">\n";
      if ($prefs{"ap_show_posted_by"}) {
	  $posted =~ s!( on )(.*[AP]M)!$1.reformat_time($2)!e;
	  print "$posted\n";
      }

      print "<div>$dept</div>\n" if ($prefs{"ap_show_department"});
      print "</div>\n";
      print "$story$story_link<br>\n" if ($prefs{"ap_show_story"});
      $shownblurb = 1;

      # bail out to the comments part
      last;
    }
  }

  (!$header) && show_header("Comments [could not parse title]");

  # Show the threshold change options

  if ($prefs{"ap_threshold_options"} && $shownblurb)
  {
    print "<div class=\"subtitle toppad\">\nShowing comments at threshold " . $prefs{"threshold"};
    if (!$prefs{"no_compressed_comments"} && $prefs{"compressed_characters"} && $prefs{"threshold"} >= 2) {
	print " and summaries at " . ($prefs{"threshold"}-1);
    }
    print(".\n");
    my $urldata = cgi_param("comments");
    print("<form method='GET' action='$self_url'>\n".
	  "<input type=hidden name=comments value='$urldata'>\n".
	  "Change to: ".
	  "<select name='threshold'  onchange='this.form.submit()'>\n");
    foreach my $num (0..5) {
	my $selected = ($prefs{"threshold"} == $num) ? " selected" : "";
	print(" <option$selected value='$num'>&nbsp;$num&nbsp;</option>\n");
    }
    print "</select></form>\n</div>";
  }
  print("</div><!--item-->\n");


  ##### and now the comments #####
  print("\n\n");
  my ($author, $score, $score_num, $message, $sid, $cid);
  my $j;
  my $uldepth = -1; # keep track of comment indentation
  my $current_title = "<blah>";
  $j=0;
  for (; $i < $elements; $i++)
  {
    $_ = $bits[$i];
    filterline();
    if ($prefs{"debugging"} >= 2) { dumpline(); }

    # keep track of UL indentation level
    my $n_ul_open = () = $_ =~ m!<ul!gi;
    my $n_ul_close = () = $_ =~ m!</ul!gi;
    if ($n_ul_open || $n_ul_close) {
	$uldepth += $n_ul_open - $n_ul_close;
	$prefs{"debugging"} && debug_msg("uldepth", $uldepth);
    }
    
#    if (m!<div class=\"title\"> <h4><a id=\".+?>(.+?)</a> <span id=\"comment_score_\d+?\" class=\"score\"> ?\(<.+?>Score:(.+?)\)</span></h4> </div>!) 
    if (m!<div class=\"title\"> <h4><a rel=\".+?>(.+?)</a> <span id=\"comment_score_\d+?\" class=\"score\"> ?\(<.+?>Score:(.+?)\)</span></h4> </div>!) 
    {
      $title = remove_tags($1);
      $score = remove_tags($2);
      $score_num = $score;
      $score_num =~ s!,.*$!!; # keep the numeric value only

      if ($prefs{"debugging"}) {
	  debug_msg("title", $title);
	  debug_msg("score", $score);
	  debug_msg("score_num", $score_num);
      }

      
      if (m!sid=([0-9]+)[^\"]+cid=([0-9]+)!)
      {
	  $sid = $1;
	  $cid = $2;
	  debug_msg("cid,sid", "$cid,$sid") if ($prefs{"debugging"});
	  if (!$prefs{'no_compressed_comments'} && $first_js) {
	      my $js = file_contents('expandmsg.js');
	      $js =~ s!<--.*?-->!!g;
	      $js =~ s!<SID>!$sid!;
	      $js =~ s!<SELF_URL>!$self_url!g;
	      $js =~ s!<THRESHOLD>!$prefs{'threshold'}!g;
	      print("<script type=\"text/javascript\">".$js."</script>\n");
	      $first_js = 0;
	  }
	  if ($cid == $thr_cid) {
	      $thr_title = "$title $thr_title";
	  }
      }
    }
    #  <div class="details"> <><>by <><>NAME <>(12345)<><> ...
    elsif (m!<div class="details">! && s!<[^>]+>!!g) 
    {
	  s!([AP]M).*$!$1!g;
	  s!writes:.*on !on !g;
	  s!writes:!!g;
	  $author = "Posted $_";
  	  debug_msg("author", $author) if ($prefs{"debugging"});
    }

    elsif (m!<div class="commentBody">(.+)</div>!i)
    {
      $message = remove_tags_except_basic($1);
      # Remove the "Read the rest of this comment" line and replace
      # with generic message
      if ($message =~ m!Read the rest of this comment!) {
	  my $newth = $prefs{threshold} - 1;
	  if ($newth < -1) {
	      $newth = -1;
	  }
	  my $newtext="<br><a href=\"$self_url?comments=$sid,$cid&amp;threshold=$newth#$cid\">".
	      "[Read full comment in thread]</a>";
	  $message =~ s!<a href=\"[^\"]*slashdot.org/comments[^>]+>Read the rest.*?</a>!$newtext!;
      }

      my $msg_length = length(remove_tags($message));
      if ($prefs{"debugging"}) {
	  debug_msg("message", $message);
	  debug_msg("message-length", $msg_length);
      }

      # We have everything (i hope) so clean up message
      debug_msg("Got everything...") if ($prefs{"debugging"});
      ++$commentscount;

      cleanup_message(\$message);

      if ($j <= $prefs{"max_comments"} && $score_num >= $prefs{"threshold"} - 1) {
	  my $msg_html = "";
	  
	  if (!$prefs{"no_compressed_comments"} && $score == $prefs{"threshold"} - 1) {
	      $msg_html = format_msg_abbrev($title, $score, $author, $message, $msg_length, $cid, $sid);
	      $j += 0.25; # abbreviated messages count as less
	  }
	  elsif ($score >= $prefs{"threshold"}) {
	      # heuristics to decide whether to add a '[thread]' link
	      my $title_nore = $title;
	      $title_nore =~ s!^Re:\s*!!;
	      my $add_thread_link = $prefs{'extra_links'};
	      if ($title_nore ne "" && $title_nore ne $current_title) {
		  $add_thread_link = 1;
		  $current_title = $title_nore;
	      }
	      # and output unabbreviated message
	      if ($author !~ /on.*[PA]M/ && $msg_length > 500) {
		  $msg_html .= format_msg($title, $score, $author, $message,
					  $msg_length, 1, $cid, $sid, $add_thread_link);
	      }
	      else {
		  $msg_html .= format_msg($title, $score, $author, $message,
					  $msg_length, 0, $cid, $sid, $add_thread_link);
	      }
	  }
	  if ($msg_html ne "") {
	      embed_div_inX($uldepth, \$msg_html);
	      print("$msg_html\n\n");
	      ++$j;
	  }
      } else {
	  if ($prefs{"debugging"} && $j > $prefs{"max_comments"}) {
	      debug_msg("Skipped due to $j > max_comments.\n");
	  }
	  elsif ($prefs{"debugging"} && $score_num < $prefs{"threshold"}-1) {
	      debug_msg("Skipped due to score $score_num < " . $prefs{"threshold"}-1);
	  }
	  elsif ($prefs{"debugging"}) {
	      debug_msg("Skipped.\n");
	  }
      }
      $author = $score = $author = $message = $cid = "";
    }
  } # for $i $elements
  if ($j == 0) {
      print "<p><small><b>There are no comments rated $prefs{threshold} or higher.</b></small></p>";
    } elsif ($j >= $prefs{"max_comments"})  {
      print "<p><small><b>Only the first " . $prefs{"max_comments"} . " comments are shown here.</b></small></p><hr>";
    }
  status_message(1);
  if ($thread_mode) {
      print_bookmark_link($thr_title);
  }
  my $extra_footer_html = "";
  if (!$prefs{'extra_links'}) {
      my $urldata = cgi_param("comments");
      $extra_footer_html =
	  "<a href=\"$self_url?comments=$urldata\&amp;threshold=$prefs{threshold}\&amp;xlinks=1\">".
	  "[Show extra thread/reply links]</a><br>";
  }
  print_ckupdate_js();
  (!$shownblurb || $commentscount == 0) && print_ckupdate_link("Slashdot comments page");
  show_footer(0, $extra_footer_html);
}


# poll bar result (as string)
sub mk_pollbar
{
    my ($percent, $poll_item) = @_;
    return sprintf(
	"<span class=\"pollbar\"><span class=\"bar\" style=\"width:%d%%\">&nbsp;</span>".
	"&nbsp;%d%%</span>&nbsp;&nbsp;%s<br>\n", $percent*1.3, $percent, $poll_item);
    # note: $percent*1.3 is because it's rare to have > 75%.
    # But reserve some space for the actual percentage.
}


# cleanup unnecessary HTML markup from raw slashdot html code.
# also add some line breaks and other minor changes for easier line-by-line parsing later on.
# operates in-place on ref to string with HTML code.
sub correct_formatting
{
  my $Rpage = shift;

  # Advert removal
  $$Rpage =~ s!<\!-- advertisement code\. -->.+?<\!-- end ad code -->!!gis;
  $$Rpage =~ s!<P><TABLE.+?ad\.doubleclick\.net.+?</NOSCRIPT></TD></TR></TABLE>!!gis;

  # More generic removal of scripts, iframes, css
  $$Rpage =~ s!<script .+?</script>!!gis;
  $$Rpage =~ s!<noscript.+?</noscript>!!gis;
  $$Rpage =~ s!<iframe.+?</iframe>!!gis;
  $$Rpage =~ s!<style.+?</style>!!gis;

  # reduce whitespace
  $$Rpage =~ s!\s+! !g;

  # Change some CSS to <blockquote> for ease of replacing later on.

  $$Rpage =~ s!<div class="quote">(.+?)</div>!<blockquote>$1</blockquote>!gis;

  ## Change comments where quotes have been prefixed with > to <blockquote>
  $$Rpage =~ s!<p>&gt;(.+?)</p>!<blockquote>$1</blockquote>!gis;

  # Insert newlines at the beginning of <div class=...> to make parsing as
  # simple as possible.

  $$Rpage =~ s!(<div class.*?>)!\n$1!gis;


}  

# arg 1: show issues, boolean
# arg 2 (opt): extra html code 
sub show_footer
{
  my $show_issues = shift;
  my $extra_html = "";
  if ($#_ >= 0) {
      $extra_html = shift;
  }
  my $when = strftime($prefs{'time_fmt'}, localtime($fetch_info{pagedate} + $prefs{'tzoffset'}));
  my $ago = format_time_interval(time() - $fetch_info{pagedate}, 0);
  
  print("<div class=\"footer\" id='page-bottom'>\n");
  if ($show_issues) { print_issue_links(); }
  print($extra_html);


  #why this doesn't work in FF???
  print("<div class='scroll'>".
	"<a href='#page-top' onclick='return as_scroll(-10)'>&nbsp;&#x21E7;&nbsp;</a><br><br>".
	"<a href='#page-bottom' onclick='return as_scroll(10)'>&nbsp;&#x21E9;&nbsp;</a>".
	"</div>\n");
  
  print("<div>Avantslash v$version - ".
	"<a href=\"$self_url?showcredits=1\">About</a> - ".
	"<a href=\"$self_url?showprefs=1\">Preferences</a> - \n".
	"<a href=\"$self_url?showbm=1\">Bookmarks</a><br>\n".
	"Page collected on $when ($ago ago)\n".
	"</div></div></body></html>\n");
}


# show header.
# arguments: title, [timeout-minutes]

sub show_header
{
  my $title = shift;
  my $timeout
      = (defined($_[0]) ? $_[0] : $prefs{"cache_timeout"}) * ONE_MINUTE;

  # Remove any tags in the title
  $title =~ s/<.+?>//g;

  # Headers
  print "Cache-control: max-age=$timeout\n";
  print "Vary: Cookie\n"; # cookie value may contain CSS setting
  print_content_type_html();

  # Work out what the stylesheet should be
  my $cssname = get_stylesheet();
  
  print
      "<!DOCTYPE HTML>\n".
      "<html>\n<head>\n<title>$title</title>\n";
  ($cssname ne "bare") &&
      print "<link href='$self_url?css=$cssname' rel='StyleSheet' type='text/css' media='handheld,screen,all'>\n";
  print("<script type='text/javascript'>".
	"function as_scroll(n){window.scrollBy(0, n*window.innerHeight);return false;}".
	"</script>\n");

  # Site icons
  my $icon_name = $prefs{soylent} ? "favicon-S.ico" : "favicon.ico"; 
  print "<link rel=\"shortcut icon\" href=\"$icon_name\" type=\"image/x-icon\">\n";
  my $user_agent = get_UA();
  # common UAs: http://www.zytrax.com/tech/web/mobile_ids.html
  if ($user_agent =~ m!Android!i) {
      # Android 2+ supports this, but Android 2.x needs absolute path
      # http://code.google.com/p/android/issues/detail?id=7657
      my $basepath = "//".$ENV{HTTP_HOST}.$self_url;
      $basepath =~ s!/[^/]+$!!;
      print "<link rel=\"apple-touch-icon-precomposed\" href=\"$basepath/apple-touch-icon-iphone.png\" />\n";
  }
  if ($user_agent =~ m!\b(iPad|iPhone|iPod)\b!i) {
      # Apple only
      print "<link rel=\"apple-touch-icon\" href=\"apple-touch-icon-iphone.png\" />\n";
      print "<link rel=\"apple-touch-icon\" sizes=\"72x72\" href=\"apple-touch-icon-ipad.png\" />\n";
      print "<link rel=\"apple-touch-icon\" sizes=\"114x114\" href=\"apple-touch-icon-iphone4.png\" />\n";
  }

  # other stuff
  if ($prefs{"debugging"}) {
      print "<style class='text/css' media='handheld,screen,all'>\n";
      print "pre { color:#888; font-size:0.85em; margin:0em; white-space:pre-wrap; }\n".
	  "pre em { color:#66a; font-style: normal; }\n".
	  "p.filt { color:#855; font-size:0.85em; }\n".
	  ".debug { color:#585; font-size:0.85em; }\n";
      print "</style>\n";
  }
  print "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1.0\" />\n";
  # prevent interpeting user ids as phone numbers 
  print "<meta name=\"format-detection\" content=\"telephone=no\">\n";

  if ($prefs{'demo_mode'} || get_UA() =~ /(bot\b|spider|crawler)/i) {
      print "<meta name=\"robots\" content=\"noindex,nofollow\">\n";
  }
  print "</head>\n<body id='page-top'>\n";

  ($prefs{debugging}) && 
      print("Raw HTML fetch: url=$fetch_info{url}, cache=$fetch_info{cache}<br>\n");


  print("<div class=\"header\">\n".
	"<div class=\"logobar\"><a href=\"$self_url\"><span class=\"logo\"><span>Slashdot</span>".
	"&nbsp; &nbsp; &nbsp; ". # Ensure that it can be hovered by keyboard-only browsers.
	"</span></a></div>\n".
	"</div>\n"
	);

  $prefs{'demo_mode'} &&
      print "<div class='error'; style='text-align:center;'>".
      "Avantslash demo mode; restricted functionality.".
      "<a href='$self_url?showcredits=1'>More info</a></div>\n";
  
}


# takes reference to text and modifies in place
sub repoint_urls
{
  my $Rtxt = shift;

  $$Rtxt =~ s!"(https?://.+?)"!'"'.repoint_one_url($1).'"'!egis;
  $$Rtxt =~ s!"(//.+?)"!'"'.repoint_one_url($1).'"'!egis;
  $$Rtxt =~ s!href="(/[^/].*)"!'href="'.repoint_one_url($1).'"'!egis;

  # Shorten stupidly long URL's too, but only if the text being
  # hyperlinked has no spaces in it.
  
  $$Rtxt =~ s#<a href="?(.+?)>(.+?)</a>#shorten_url($1,$2)#egis;
}

# shorten_url
# Takes a URL and works out whether or not the hyperlinked text is
# very long and contains no spaces. If so, then it returns the very
# same URL but with shorter text to avoid scrolling. This function is
# pretty messy as I couldn't get a single regexp to match to all the
# possible combinations of hyperlinks.

sub shorten_url
{
  my $url = shift;
  my $text = shift;
  my $tags;
    
  # Check that url contains tags, if it does then remove them from
  # $url and put them into $tags.
  
  if ($url =~ /(.+?)[\" ](.+)/)
  {
    $url = $1;
    $tags = $2;
  }
  
  # Remove any quotes from the URL so that we can add them back
  # in later in a uniform way.
  
  $url =~ s/\"//g;
  
  # if the text has no spaces and is over 50 characters long, then
  # let us shorten it so that you don't have to scroll sideways.
    
  if (index($text, " ") == -1 && length($text) > 50)
  {  
    $text = substr($text, 0, 22) . "..." . substr($text, length($text)-22, 22);
  }
  
  return "<a href=\"$url\"$tags>$text</a>";
}


# input: generic URL without quotes (http://.....)
# return: mobile-friendly URL if possible
sub repoint_one_url
{
  my $url = shift;

  # If someone references another slashdot article (say, it's a dupe)
  # then lets make sure that the link is parsed by avantify.
  # also deal with other common websites that have mobile versions:
  # xkcd.com, wikipedia.org


  if ($prefs{'soylent'}) {
      if ($url =~ m!soylentnews.org/article.pl\?sid=(\d\d/\d\d/\d\d/\d+)!) {
	  return "$self_url?comments=$1";
      }
      if ($url =~ m!soylentnews.org/comments.pl\?.*sid=(\d+)&cid=(\d+)!) {
	  return "$self_url?comments=$1,$2";
      }
      if ($url =~ m!soylentnews.org/comments.pl\?.*sid=(\d+)!) {
	  return "$self_url?comments=$1,0";
      }

  } else {
    # slashdot links
    if ($url =~ m!slashdot\.org/.*/(\d\d/\d\d/\d\d/\d+)!) {
      return "$self_url?comments=$1";
    }
    if ($url =~ m!slashdot\.org/comments.pl\?sid=(\d+)\&(amp;)?cid=(\d+)!) {
        return "$self_url?comments=$1,$3&amp;threshold=1";
    }
    if ($url =~ m!^(/[^/].*)! && $url !~ /$self_url/) {
	return "https://m.slashdot.org$url";
    }
  }

  if ($url =~ m!^(https?://)(xkcd.com/[0-9]+/)$!) {
      return "$1m.$2";
  }

  if ($url =~ m!^(https?://[a-z]+)\.(wikipedia\.org/wiki/.*)$!) {
      return "$1.m.$2";
  }

  if ($url =~ s!^(https?://)(www\.)?youtube\.com/!$1m.youtube.com/!) {
      return $url;
  }
  
  return $url; 
}

#### bookmark stuff ####

sub print_bookmark_link
{
    my ($title) = @_;
    if ($prefs{'demo_mode'}) {
	return;
    }
    $title =~ s!'!&#39;!g;
    my $sid_cid = cgi_param('comments');
    $sid_cid =~ s/[^\d,]//gs;
    print("<form action='$self_url' method='post'>\n".
	  " <input type='hidden' name='bookmark' value='$sid_cid'>\n".
	  " <input type='hidden' name='bmtitle' value='$title'>\n".
	  " <input type='hidden' name='threshold' value='$prefs{threshold}'>\n".
	  " <button>Bookmark this thread</button>\n".
	  "</form>\n");
}
sub read_bookmarks
{
    # read bookmarks from file
    # argument: hash reference (key:'sid,cid'; value:'timestamp:title')
    my $Rbm = shift;
    my $fh;
    if (!open($fh, "cache/bookmarks-0.txt")) {
	return;
    }
    while (<$fh>) {
	if (/^#/) { next; }
	chomp();
	if (/^(\d+,\d+):(.*)$/) {
	    $Rbm->{$1} = $2;
	}
    }
    close($fh);
}

sub write_bookmarks
{
    # write bookmarks to file
    # argument: hash reference
    my $Rbm = shift;
    my $fh;
    if (!open($fh, ">cache/bookmarks-0.txt")) {
	fatal_error("Cannot write bookmarks.");
    }
    print($fh "#Bookmarks file\n");
    foreach my $k (keys(%$Rbm)) {
	print($fh "$k:".$Rbm->{$k}."\n");
    }
    close($fh);
}

sub set_bookmark
{
    my $sid_cid = cgi_param("bookmark");
    my $title = cgi_param("bmtitle");
    my $threshold = cgi_param("threshold");
    $sid_cid =~ s/[^\d,]//sg;
    $title =~ s/[\000-\037<>&]//sg;
    $threshold =~ s/[^0-5]//sg;
    if ($threshold eq "") { $threshold = $prefs{'threshold'}; }

    my %bm = ();
    read_bookmarks(\%bm);
    $bm{$sid_cid} = time().":$threshold:$title";
    write_bookmarks(\%bm);
    redir_bookmarks();
}

sub del_bookmark
{
    my $sid_cid = cgi_param("delbm");
    my %bm;
    read_bookmarks(\%bm);
    if (exists($bm{$sid_cid})) {
	delete($bm{$sid_cid});
	write_bookmarks(\%bm);
    }
    redir_bookmarks();
}

sub redir_bookmarks
{
    my $redir_url = "//" .$ENV{'HTTP_HOST'} ."$self_url?showbm=1";
    print("Status: 302 moved\n");
    print("Location: $redir_url\n");
    print_content_type_html();
    print("Go to <a href='$redir_url'>$redir_url</a>\n");
}


sub show_bookmarks
{
    my %bm;
    read_bookmarks(\%bm);

    show_header("Bookmarks", 0);
    print("<h2>Bookmarks</h2>\n");
    my $tm_fmt = $prefs{'time_fmt'};
    $tm_fmt =~ s/,?\s*%[HI]:.*//; # no hours, minutes
    if ($tm_fmt !~ /%/) { $tm_fmt = '%F'; }

    if (keys(%bm) > 0) {
	print("<table class='bm'>\n");
	foreach my $sid_cid (sort { $bm{$b} cmp $bm{$a} } keys(%bm)) {
	    my ($tm, $threshold, $title) = split(/:/, $bm{$sid_cid}, 3);
	    my $tm_str = strftime($tm_fmt, localtime($tm + $prefs{'tzoffset'}));
	    my $url1 = "$self_url?comments=$sid_cid&amp;threshold=$threshold";
	    my $url2 = "$self_url?delbm=$sid_cid";
	    print(" <tr><td>$tm_str <td><a href='$url1'>$title</a>".
		  "<td>&nbsp;<a href='$url2' class='del'>[del]</a>\n");
	}
	print("</table\n");
    } else {
	print("<p>You have no bookmarks. To add a bookmark, view a comment thread and ".
	      "tap 'bookmark this thread' at the bottom.\n");
    }
    print_ckupdate_js();
    print "<div class='footer'><a href=\"$self_url\">Back to main page</a></div>";

    print "</div></body></html>";
}


#### other stuff ####

sub show_credits
{
  my @missing_vars = @_;
  show_header("About Avantslash", 0);
  if ($prefs{'demo_mode'}) {
      print("<h2>Avantslash demo info</h2>\n");
      print(file_contents("demo-info.txt"));
  }
  print("<h2>Copyright</h2>\n");
  my $cr_fname = "copyright-avantslash.txt";
  my $copyright_html = (-f $cr_fname)
      ? file_contents($cr_fname)
      : "File $cr_fname missing: copyright R. Lawrence/H.K. Nienhuys; see http://www.fourteenminutes.com/code/avantslash/ .";
  $copyright_html =~ s!<THISYEAR>!$thisyear!g;
  $copyright_html =~ s!<VERSION>!$version!g;
  $copyright_html =~ s!<SELF_URL>!$self_url!g;
  print($copyright_html);
  
  ## diagnostic information
  my $missing_var_html = "";
  if ($#missing_vars >= 0)
    {
        $missing_var_html = "<dt>Missing configuration parameters</dt>".
  	  "<dd>".join(", ", @missing_vars)."</dd>\n";
    }
  
  my $UA = get_UA();
  if (!defined($UA) || $UA eq "") { $UA = "Unknown"; }
  my $cookiecss = CGI::cookie("css");
  my $cssfile = get_stylesheet();

  if (!defined($cookiecss)) { $cookiecss = "Not set."; }
  print("<h2>Diagnostic information</h2>\n".
        "<dl>\n".
        "<dt>Your browser User-Agent</dt><dd>$UA</dd>\n".
        "<dt>Style sheet setting<dd>\n".
	"  Configuration: $prefs{default_stylesheet}<br>\n".
	"  Cookie: $cookiecss<br>\n".
	"  Actual: $cssfile\n".
	$missing_var_html);

  if (!$prefs{'demo_mode'}) {
      print("<dt>Cache statistics\n".
	    "<dd>\n");
      show_cache_status();
  }
  print("</dl>\n");
  if ($prefs{debugging}) {
      print("<h2>Configuration settings (debug)</h2>\n");
      foreach my $key (sort { $a cmp $b } keys(%prefs)) {
  	print("$key ".$prefs{$key}."<br>\n");
      }
      
  }
  
  print_ckupdate_js();
  print "<div class='footer'><a href=\"$self_url\">Back to main page</a></div>";

  print "</div></body></html>";

}

sub show_prefs
{
  my @missing_vars = @_;
  show_header("Avantslash preferences", 0);

  # referrer
  my $ref_url = cgi_param("referer");
  if ($ref_url eq "" && defined($ENV{"HTTP_REFERER"})) {
      $ref_url = $ENV{"HTTP_REFERER"};
      $ref_url =~ s/\&/\&amp;/g;
  }
  
  ##### CSS selection
  my $cssfile = get_stylesheet();
  # list of css files: base (a) and mods (b)
  # key=name, value=description
  my %csslist_a = ("reset", "Reset to default value");
  my %csslist_b;
  foreach my $cssindex ("css_dist.txt", "css_local.txt") {
      (-f $cssindex) || next;
      open(my $cssfh, $cssindex);
      while (<$cssfh>) {
	  (/^\#/ || /^\s*$/)  && next;
	  chomp();
	  my $cssfile = $_;
	  my $cssdesc;
	  if (! -f "css/$cssfile") {
	      $cssdesc = "<span class='error'>Not available! (check css_*.txt)</span>";
	  } else {
	      my $cssdata = file_contents("css/$cssfile");
	      $cssdesc = "";
	      if ($cssdata =~ m@/\*\s*\!ABOUT:(.*)\*/@) {
		  $cssdesc = "$1";
	      }
	  }
	  $cssfile =~ s!\.css$!!;
	  if ($cssdesc =~ s/!MOD(:(\d+))?//) {
	      my $sortval = defined($2) ? $2 : "9";
	      $csslist_b{"$sortval:$cssfile"} = $cssdesc;
	  } else {
	      $csslist_a{$cssfile} = $cssdesc;
	  }
      }
  }      
  print("<h2>Skin selection</h2>\n");
  print("<form method='POST' action='$self_url?setcss=1'>\n".
	"<input type='hidden' name='setcss' value='1'>\n");

  if ($ref_url ne "") {
      print("<input type='hidden' name='referer' value='$ref_url'>\n");
  }

  print("<b>Base skin</b><br>\n");
  foreach my $name (sort {$a cmp $b} keys(%csslist_a)) {
      my $checked = ($cssfile =~ /\b$name\b/) ? "checked='checked'" : "";
      print("<input type='radio' name='base' value='$name' $checked><b>$name</b>: $csslist_a{$name}<br>\n");
  }
  print("<b>Options</b><br>\n");
  foreach my $xname (sort {$a cmp $b} keys(%csslist_b)) {
      my $name = $xname;
      $name =~ s/^\d+://;
      my $checked = ($cssfile =~ /\b$name\b/) ? "checked='checked'" : "";
      print("<input type='checkbox' name='mod' value='$name' $checked><b>$name</b>: $csslist_b{$xname}<br>\n");
  }
  print("<input type=submit value='Apply'>\n".
	"<input type=submit name='return' value='Apply and return'><br>\n".
	"</form>\n");
  print("<p>You may have to reload some pages for the change to take effect.");
  
  print_ckupdate_js();
  print "<div class='footer'><a href=\"$self_url\">Back to main page</a></div>";

  print "</div></body></html>";

}

# remove onclick etc. from tags in $_
sub filterline {
    s!(<[^>]*)\bonclick=\"[^\"]+\"!$1!g;
}


# dump current $_ as <pre> after filtering
sub dumpline {
    my $line_filt = $_; # useless attributes removed 
    my $line_filt2 = $line_filt; # all <...> tags removed
    $line_filt =~ s!(.<div|<li>|<p\b|<input\b)!\n  $1!g;
    $line_filt =~ s!(<[^>]+>)!tag_attr_filter($1)!ge;
    #$line_filt =~ s!<a href=\"[^\"]+\"!<a href=\"...\"!g;
    $line_filt =~ s!(<[^>]+class=\"[^ \"]+ )[^\"]+!$1...!g;
    $line_filt =~ s!\&!\&amp;!g;
    $line_filt =~ s!<!&lt;!g;
    $line_filt =~ s!>!&gt;!g;
    $line_filt =~ s!(\&lt;.*?\&gt;)!<em>$1</em>!g;
    $line_filt2 =~ s!<[^>]+>!!g;
    print("<pre>&para;$line_filt</pre>\n");
    print("<p class=\"filt\">$line_filt2></p>\n");
    if ($line_filt2 =~ /<!--/) { print("-->\n"); } 
    
}

# remove all <...> tags
sub remove_tags {
    my $x = shift;
    $x =~ s!<(br|p)[^>]*>! !ig;
    $x =~ s!<[^>]+>!!g;
    return $x;
}

# input: one tag, e.g. <a href="blah" onclick="blah">
# return tag <...> with irrelevant attributes stripped
sub tag_attr_filter {
    my $tag = shift;
    if ($tag =~ m!^<(\S+)(\s.*)?>$!) {
	my $tagname = $1; # the 'a' or 'div' part
	my $attribs = $2;
	$attribs =~ s!
	    \b(src|width|height|style|rel|onclick|title|alt|target|name|[a-z]+:[a-z]+) # attr. names
	    =\"[^\"]*\" # attr. values
	    !ZZZ!gx;
	$attribs =~ s!ZZZ(\s*ZZZ)*!...!g;
	return "<$tagname$attribs>";
    } else {
	return $tag;
    }
}

# input: one tag, e.g. <a href="blah">
# return tag <...> if allowed, empty string if not allowed.
sub tagfilter {
    my $tag = shift;
    $tag =~ s/^<(.*)>$/$1/;
    my $is_closing = ($tag =~ s!^/!!) ? "/" : "";
    my $tag1 = ($tag =~ m!^(\S+)!) ? $1 : "??"; # the 'a', 'br' etc. part
    if ($tag1 !~ /^(a|p|b|i|em|br|blockquote|ul|ol|li|h4)$/) { return ""; }
    if ($tag1 eq "a" && $tag =~ m!(href=\"[^\"]+\")!) {
	# keep the href
	$tag1 .= " $1";
    }
    return "<$is_closing$tag1>";
}

# remove all <...> tags except <a href='...'>...</a>, <p>, <b>, <em>, <i>, <br>, <blockquote>
sub remove_tags_except_basic {
    my $x = shift;
    $x =~ s!(<[^>]+>)!tagfilter($1)!ge;
    return $x;
}

# debug message: print string value with html specials escaped
sub debug_msg {
    if ($#_==1) {
	my ($name, $value) = @_;
	$value =~ s!\&!&amp;!g;
	$value =~ s!<!&lt;!g;
	$value =~ s!>!&gt;!g;
	$value =~ s!&lt;([^\&]+)&gt;!<b>&lt;$1&gt;</b>!g;
	$value =~ s!\n!<br> &nbsp; \n!g;
	print("<span class='debug'><b>$name</b> = [$value]<br></span>\n");
    } else {
	print("<span class='debug'><b>&gt;&gt; </b>", @_, "<br></span>\n");
    }
}

# return html code for abbreviated message  (slashdot, via ajax)
sub format_msg_abbrev
{
    my ($title, $score, $author, $message, $msg_length, $cid, $sid) = @_;
    my $orig_message = $message;
    $message =~ s!<blockquote>.*?</blockquote>!(...) !g;
    $message = substr(remove_tags($message), 0, $prefs{"compressed_characters"})."..";
    if ($msg_length > 500) { $message .= ".."; }
    my $max_ti_len = int(13 + 0.1 * $prefs{"compressed_characters"});
    if (length($title) > $max_ti_len) {
	$title = substr($title, 0, $max_ti_len - 3)."...";
    }
    my $html = "<div class=\"item abbr\"><span class=\"title\">$title</span>  $message <EXPAND></div>";
    ajaxify_message(\$html, $cid, $sid);
    return  $html;
}

# return html code for abbreviated message (Soylent, via hidden)
sub format_msg_abbrev_soylent {
    my ($title, $score, $author, $message, $msg_length, $cid, $sid) = @_;
    my $full_html = format_msg($title, $score, $author, $message, 0, $msg_length, $cid, $sid);
    
    $message =~ s!<blockquote>.*?</blockquote>!(...) !g;
    $message = substr(remove_tags($message), 0, $prefs{"compressed_characters"})."..";
    if ($msg_length > 500) { $message .= ".."; }
    my $max_ti_len = int(13 + 0.1 * $prefs{"compressed_characters"});
    if (length($title) > $max_ti_len) {
	$title = substr($title, 0, $max_ti_len - 3)."...";
    }
    my $expand_code = "<a href='#' onclick='return expand_comment($cid)'>[expand]</a>";
    my $short_html = "<div class=\"item abbr\"><span class=\"title\">$title</span> $message $expand_code</div>";
    return "<div class='abb-comment' id='ac$cid'>\n$short_html\n</div>\n".
	"<div class='exp-comment' id='ec$cid'>\n$full_html</div>\n";
    
}



# return html code for full message, add [expand] if necessary and if $use_ajax
sub format_msg
{
    my ($title, $score, $author, $message, $msg_length, $use_ajax, $cid, $sid, $add_thread)
	= @_;
    my $threadlink = "";
    if (($add_thread || $prefs{'extra_links'} || $title !~ /^re:/i) && $cid != 0) {
	my $th = $prefs{'threshold'} - 1;
	if ($th < 0) { $th = 0; }
	$threadlink = "  <a href='$self_url?comments=$sid,$cid&amp;threshold=$th'>[thread]</a>";
    }

    my $replylink = "";
    if ($prefs{'extra_links'}) {
	my $url = ($prefs{'soylent'}) ? "https://soylentnews.org" : "https://slashdot.org";
	$url .= "/comments.pl?sid=$sid\&amp;op=Reply\&amp;pid=$cid";
	$replylink = " <a href=\"$url\">[reply]</a>";
    }

    my $has_timestamp = ($author =~ s!( on )(.*[AP]M)!$1.reformat_time($2)!e);
    
    my $html =
	"<div class=\"item\">\n".
	"<h3>$title (score: $score)</h3>\n".
	"<div class=\"subtitle\">$author$threadlink$replylink</div>\n".
	"$message";
    
    # detect truncated comments. Cutoff level seems to be 512 characters (plus or minus a few),
    # not including HTML code. Truncation is always in nested messages.
    if ($use_ajax && !$has_timestamp && $msg_length > 500) {
	ajaxify_message(\$html, $cid, $sid);
    }
    $html .= "</div>\n";
    return $html;
}

# embed argument (ref) in <div class="in#">...</div>, depending on  $uldepth argument
sub embed_div_inX {
    my ($uldepth, $Rdata) = @_;
    if ($uldepth >= 1) {
	my $uld = ($uldepth <= 4) ? "in$uldepth" : "in4";
	$$Rdata = "<div class=\"$uld\">$$Rdata</div>";
    }
}


# add ajax link to end of message text, to expand this message
# arguments: reference to message string, cid, sid
sub ajaxify_message {
    my ($Rmsg, $cid, $sid) = @_;
    my $expand_html ="[<a href=\"#\" id=\"x$cid\" onclick=\"return load_comment($cid)\">expand</a>]";
    if ($$Rmsg =~ s!<EXPAND>!$expand_html!) {
	# done...
    } elsif ($$Rmsg !~ s!(</p>\s*)$!$expand_html$1!) {
	$$Rmsg .= $expand_html; # append to message
    }
    $$Rmsg = "<div id=\"cmt$cid\">$$Rmsg\n</div>";
}

# get single comment text and output over HTTP.
# assume the global $page is already set-up.
sub parse_ajax_comment {
    # get cid, sid
    my ($cid,$sid) = (0,0);
    if ($_[0] =~ m!^(\d+),(\d+)$!) {
	$cid = $1;
	$sid = $2;
    }

    # inherit xlinks setting from referrer; that saves a lot of work
    my $refer = $ENV{'HTTP_REFERER'};
    if (!defined(CGI::param('xlinks')) && defined($refer) && $refer =~ /\bxlinks=([01])\b/) {
	$prefs{'extra_links'} = $1;
    }

    
    my $rawhtml = $page;
    print("Vary: Referer\n"); # because xlinks query parameter should be inherited
    print_content_type_html();
    
    # de-escape all the javascript stuff
    $rawhtml =~ s!\\\"!\"!g;
    $rawhtml =~ s!\\n!\n!g;
    $rawhtml =~ s!\\t! !g;
    if ($prefs{"debugging"}) {
	debug_msg("Data", $rawhtml);
	print("<br>");
    }
    # find the relevant data
    my ($title, $author, $score, $date, $body) = ("title?", "author?", "score?", "date?", "body?");
    if ($rawhtml =~ m!class=\"score\">.*?>Score:(.*?)\)<!) {
	$score = remove_tags($1);
	debug_msg("score", $score) if ($prefs{"debugging"});
    }
    if ($rawhtml =~ m!<h4[^>]*>(.*?)</a>!) {
	$title = remove_tags($1);
	$title =~ s!^Re:!Re: !;
	debug_msg("title", $title) if ($prefs{"debugging"});
    }
    if ($rawhtml =~ m!\"byby\">(by .*? on .*?[AP]M)!s) {
	$author = remove_tags($1);
	$author =~ s!writes:!!;
	debug_msg("author", $author) if ($prefs{"debugging"});
    }
    if ($rawhtml =~ m!commentBody\">(.*)<div class=\"commentSub!s) {
	$body = $1;
	$body =~ s!<div class=\"quote\">(.+?)</div>!<blockquote>$1</blockquote>!gis;
	$body = remove_tags_except_basic($body);
	cleanup_message(\$body);
	debug_msg("body", $body) if ($prefs{"debugging"});
    }
    $body .= status_message(0);
    print(format_msg($title, $score, $author, $body, 0, 0, $cid, $sid, 0, $prefs{'extra_links'}));
}

# check updates, output page
sub parse_ckupdate {
    my $mode = shift; #1=page, 2=javascript
    my ($release_vrsn, $release_date, $release_summary) = ("", "", "");
    my $ok = 0;
    my $message = "";
    if ($page =~ m!^500 TIMEOUT!) {
	$message = "Timeout while retrieving the latest version number".
	    ($mode == 1 ? " from $fetch_info{url}." : ".");
    } else {
	if ($page =~ m!^version=(.*?)$!m) { $release_vrsn = $1; }
	if ($page =~ m!^date=(.*?)\s*$!m) { $release_date = $1; }
	if ($page =~ m!^summary=(.*?)\s*$!m) { $release_summary = $1; }
	$ok = ($release_vrsn ne "");
	if ($ok) {
	    $message = "The latest version is $release_vrsn ($release_date). ";
	} else {
	    $message = "Could not parse $fetch_info{url}.";
	}
    }
    if ($mode == 1) {
	show_header("AvantSlash update check");
	print("<p>You are running AvantSlash $version.<br>\n$message<br>\n");
	if ($ok && $version ne $release_vrsn) {
	    print("Changes in the latest release: $release_summary<br>");
	    if ( -f "autoupgrade.sh" ) {
		print("<form method=POST action='$self_url'>\n".
		      "You have enabled auto-upgrading.\n".
		      "<input type=hidden name=upgrade value='$release_vrsn'>\n".
		      "<input type=submit value='Upgrade now'>\n".
		      "</form>");
	    } else {
		print("<p>You did not enable auto-upgrading (autoupgrade.sh not found).\n");
	    }
	}
	print("<p>See <a href='http://avantslash.org/viewdoc.cgi/changelog'>Avantslash.org CHANGELOG</a>\n");
	
	show_footer();
    } else {
	# generate inline javascript, only if present version and release version don't match.
	my $js;
	if ($release_vrsn ne $version && $release_vrsn ne "") {
	    my $msg = "<div class=\"error\">$message".
		" you are running $version. [<a href=\"$self_url?ckupdate=1\">What\\'s new?</a>]".
		"<\/div>";
	    $js = "document.write('$msg');\n";
	} elsif ($release_vrsn eq "") {
	    $js = "// problems fetching version info from $fetch_info{url}\n";
	} else {
	    $js = "// you are running the most recent version.\n";
	}
	
	print("Content-Type: text/javascript\n".
	      "Cache-control: max-age=43200\n\n".
	      "$js\n");
    }
}

# input: reference to message string ( remove_tags_except_basic already called)
sub cleanup_message {
    my $Rmessage = shift;
    # Fix cases where there is a <blockquote> but no closing one
    my $opencount = 0;
    my $closecount = 0;
    
    my $messagecopy = $$Rmessage;
     
    $opencount++ while ($messagecopy =~ /<blockquote>/ig);
    $closecount++ while ($messagecopy =~ /<\/blockquote>/ig);
    
    while($opencount > $closecount)
    {
        $$Rmessage .= "</blockquote>";
        $closecount++;
    }
    
    # Repoint URL's
    repoint_urls($Rmessage);
}

sub file_contents
{
    my $fname = shift;
	return unless ($fname);
	
    open(my $fh, $fname) || fatal_error("$fname: $!\n");
    my @f = <$fh>;
    return join("", @f);
    close($fh);
}


# setup global %prefs according to configuration file.
# return list of missing configuration settings
sub set_configuration {
    my %kw_seen;
    my %kw_obsolete = qw(no_old_style_quoting 1);

    foreach my $configfile ("config.dist", "config.local") {
	open(CONFIG, "$configfile") || next;
	my $lineno = 0;
	# read line by line
	while(<CONFIG>)
	{
	    ++$lineno;
	    next if (/^\#/ || /^\s*$/);
	    chomp();
	    my @f = split(" ", $_, 2);
	    if ($#f != 1) { fatal_error("$configfile: line $lineno: cannot parse line.\n"); }
	    my ($kw, $val) = @f;
	    my $kw_lc = lc($kw);
	    if (!defined($prefs{$kw_lc}) and !defined($kw_obsolete{$kw_lc})) {
		fatal_error("$configfile: line $lineno: unknown setting '$kw'.\n"); 
	    }
	    
	    if (!defined($prefs_non_numeric{$kw_lc}) && $val !~ /^[0-9]+$/) {
		fatal_error("$configfile: line $lineno: keyword '$kw' must be non-negative integer (value: '$val'.\n");
	    }
	    $prefs{$kw_lc} = $val;
	    $kw_seen{$kw_lc} = 1;
	}
	close CONFIG;
    }

    ### post-processing configuration
    # Commpressed comments threshold:
    # 500 is the truncation length of slashdot; more is not meaningful.
    # max. value is 0.8 times 500.
    if ($prefs{"compressed_characters"} > 450) {
	$prefs{"compressed_characters"} = 450;
    }
    # ensure that stylesheet does not end in .css
    $prefs{"default_stylesheet"} =~ s!\.css$!!;

    # demo mode
    if (-f "DEMO_MODE" || $prefs{'demo_mode'}) {
	foreach my $k (keys(%demo_settings)) {
	    $prefs{$k} = $demo_settings{$k};
	}
    }
    # caching of ajax comments = 4x regular cache lifetime
    $cache_life_min{"ajax"} = $prefs{cache_timeout}*4;
    $cache_life_min{"ckupdate"} = $prefs{check_updates}*24*60;

    ### dealing with unseen keywords
    my @kw_unseen = ();
    foreach my $kw (keys(%prefs)) {
	if (!defined($kw_seen{$kw})) {
	    push(@kw_unseen, $kw);
	}
    }

    # setup timezone (adds a keyword, so do it after kw_unseen)
    set_tzoffset();
    $prefs{'time_fmt'} =~ s!_! !g;

    return @kw_unseen;
}

# Work out what stylesheet the user wants to use based on CGI
# parameter 'style', %prefs value, and user agent. 
sub get_stylesheet
{
    # CGI parameter always overrides any other setting
    my $cgi_style = cgi_param("style");
    if ($cgi_style ne "") {
	$cgi_style = sanitize_string_noslash($cgi_style);
	$cgi_style =~ s!\.css$!!;
	return $cgi_style;
    }

    # Cookie overrides config setting
    my $cookie_style = CGI::cookie('css');
    if (defined($cookie_style) && $cookie_style ne "dummy") {
	$cookie_style = sanitize_string_noslash($cookie_style);
	$cookie_style =~ s!\.css$!!;
	return $cookie_style;
    }
    
    return $prefs{default_stylesheet};
}

# CGI::param, but return empty string rather than undef
# also do checking for demo mode
sub cgi_param {
    my $name = $_[0];
    my $x = CGI::param($_[0]);
    if ($prefs{'demo_mode'} && defined($x)) {
	# white-listed CGI query parameters
	($name !~ m!^($demo_cgi_whitelist)$!) &&
	    fatal_error("Error: query with parameter '$name' not allowed in demo mode.\n");
	($name eq "issue" && ($x < 3 || $x > 8)) && 
	    fatal_error("Error: issues outside range 3--8 days ago not allowed in demo mode.\n");
    }
    
    if (!defined($x)) { $x = ""; }
    return $x;
}


# get environment variable; empty string if undefined
sub getenv {
    my $x = $ENV{$_[0]};
    defined($x) && return $x;
    return "";
}

# strict sanitization of string
sub sanitize_string_noslash {
    my $x = shift;
    $x =~ s![^a-zA-Z0-9.,_-]!_!g;
    return $x;
}

# sanitization of string; slash is allowed
sub sanitize_string_withslash {
    my $x = shift;
    $x =~ s![^a-zA-Z0-9,._/-]!_!g;
    return $x;
}


sub get_html {
    if (!$prefs{soylent}) {
	get_html_slashdot(@_);
    } else {
	get_html_soylent(@_);
    }
}


# get cleaned html (from cache or by http fetch); dump to output if necessary
# arguments: ref to result HTML code; type of slashdot page; slashdot url data
sub get_html_soylent {
    my ($Rhtml, $type, $urldata) = @_;

    $$Rhtml = "";

    # construct cache filename and check from cache
    my $cache_fn = "not_cached";
    if ($prefs{enable_local_cache}) {
	$cache_fn = $urldata ? "$type-$urldata.html" : "$type.html";
	$cache_fn = sanitize_string_noslash($cache_fn);
	get_file_from_cache($Rhtml, $cache_fn);
    }
    # construct URL and cache filename
    # not found in cache: construct URL and fetch over HTTP (and store in cache)
    my $slashdot_url = "no_url";
    my $timeout = $timeouts{'slashdot'}; # seconds
    if ($$Rhtml eq "") {
	# first figure out URL to fetch over HTTP
	if ($type eq "comments") {
	    if ($urldata =~ m!^poll/(\d+)!) {
		$slashdot_url = "https://soylentnews.org/pollBooth.pl?qid=$1\&aid=-1";
	    } elsif ($urldata =~ m!^(\d+),(\d+)$!)  {
		# http://soylentnews.org/comments.pl?sid=nnnn&cid=mmmm
		$slashdot_url = "https://soylentnews.org/comments.pl?sid=$1\&cid=$2\&mode=improvedthreaded\&threshold=0\&highlightthresh=0";
	    } else {
		# 
		# http://soylentnews.org/articles/aa/bb/nn/dddddd.shtml
		# http://soylentnews.org/article.pl?sid=aa/bb/cc/ddddd
		$slashdot_url = "https://soylentnews.org/article.pl?sid=$urldata\&mode=improvedthreaded\&threshold=0\&highlightthresh=0";
	    } 
	}
	elsif ($type eq "issue" || $type eq "issuedate") {
	  # timestamp in url seems to be defined relative to EDT slashdot time
	  my $datestring;
	  if ($type eq "issue") {
	      $datestring = POSIX::strftime("%Y%m%d", localtime(time()-86400*$urldata));
	  } else {
	      $datestring = $urldata;
	  }
	  $slashdot_url = "https://soylentnews.org/index.pl?issue=$datestring";
	}
	elsif ($type eq "main") {
	    $slashdot_url = "https://soylentnews.org/";
	}
	elsif ($type eq "ckupdate") {
	    my $css = get_stylesheet();
	    my $UA = uri_escape(get_UA());
	    $slashdot_url = "http://avantslash.org/".
		"checkupdate.cgi?version=$version&css=$css&ua=$UA";
	    #$slashdot_url = "//$ENV{HTTP_HOST}$self_url"; 
	    #$slashdot_url =~ s!/[^/]*$!/slow_versioninfo.cgi!; # debugging
	    $timeout = $timeouts{'avantslash'};
	}
	elsif ($type eq "search") {
	    $slashdot_url = "https://soylentnews.org/search.pl?query=".
		uri_escape($urldata)."&sort=2";
	}
	elsif ($type eq "rss") {
	    $slashdot_url = "https://rss.soylentnews.org/Slashdot/slashdot";
	}
	else {
	    fatal_error("In get_html: unknown type '$type'.\n");
	}
	# and now fetch this URL
	if ($type eq "ajax") {
	    fetch_http_ajax($Rhtml, $urldata, $timeout);
	} else {
	    fetch_http_get($Rhtml, $slashdot_url, $timeout);
	}
	# and store back into cache
	$prefs{enable_local_cache} && store_file_in_cache($Rhtml, $cache_fn);
    }

    if ($$Rhtml =~ m!AVANTSLASH_URL=(http://\S+)$!) { # url is appended to result data
	$fetch_info{url} = $1;
    }
    if ($$Rhtml =~ m!^([1-6][0-9][0-9] .{,200}?)\n! || $$Rhtml =~ m!<title>([345]\d\d .*?)</title>!) {
	$fetch_info{'statuscode'} = $1;
    }

    if ($type ne "ckupdate" && $type ne "rss") {
	correct_formatting($Rhtml);
    }
	 
    if ($prefs{"dump_reformatted_html"})
    {
	print_content_type_html();
	print $page;
	exit;
    }
}


# get cleaned html (from cache or by http fetch); dump to output if necessary
# arguments: ref to result HTML code; type of slashdot page; slashdot url data
sub get_html_slashdot {
    my ($Rhtml, $type, $urldata) = @_;

    $$Rhtml = "";

    # construct cache filename and check from cache
    my $cache_fn = "not_cached";
    if ($prefs{enable_local_cache}) {
	$cache_fn = $urldata ? "$type-$urldata.html" : "$type.html";
	$cache_fn = sanitize_string_noslash($cache_fn);
	get_file_from_cache($Rhtml, $cache_fn);
    }
    # not found in cache: construct URL and fetch over HTTP (and store in cache)
    my $slashdot_url = "no_url";
    my $timeout = $timeouts{'slashdot'}; # seconds
    if ($$Rhtml eq "") {
	# first figure out URL to fetch over HTTP
	if ($type eq "comments") {
	    if ($urldata =~ m!^poll!) {
		# http://slashdot.org/poll/nnnn/
		$slashdot_url = "https://slashdot.org/$urldata";
	    } elsif ($urldata =~ m!^(\d+),(\d+)$!)  {
		# http://slashdot.org/comments.pl?sid=nnnn&cid=mmmm
		$slashdot_url = "https://slashdot.org/comments.pl?sid=$1\&cid=$2";
	    } else {
		# http://slashdot.org/story/aa/bb/cc/zzzzzzz/ (last slash required when /. is in maintenance mode)
		$slashdot_url = "https://slashdot.org/story/$urldata/";
	    } 
	}
	elsif ($type eq "issue" || $type eq "issuedate") {
	  # timestamp in url seems to be defined relative to EDT slashdot time
	  my $datestring;
	  if ($type eq "issue") {
	      $datestring = POSIX::strftime("%Y%m%d", localtime(time()-86400*$urldata));
	  } else {
	      $datestring = $urldata;
	  }
	  $slashdot_url = "https://slashdot.org/index2.pl?".
	    "section=&color=green&index=1&view=stories&duration=-1&".
	    "startdate=$datestring&page=0";
	}
	elsif ($type eq "ajax") {
	    # ajax uses POST mechanism! handle separately
	    $slashdot_url = "https://slashdot.org/ajax.pl";
	}
	elsif ($type eq "main") {
	    $slashdot_url = "https://slashdot.org/";
	}
	elsif ($type eq "ckupdate") {
	    my $css = get_stylesheet();
	    my $UA = uri_escape(get_UA());
	    $slashdot_url = "http://avantslash.org/".
		"checkupdate.cgi?version=$version&css=$css&ua=$UA";
	    #$slashdot_url = "//$ENV{HTTP_HOST}$self_url"; 
	    #$slashdot_url =~ s!/[^/]*$!/slow_versioninfo.cgi!; # debugging
	    $timeout = $timeouts{'avantslash'};
	}
	elsif ($type eq "search") {
	    $slashdot_url = "https://slashdot.org/index2.pl?fhfilter=".
		uri_escape($urldata);
	}
	elsif ($type eq "rss") {
	    $slashdot_url = "http://rss.slashdot.org/Slashdot/slashdot";
	}
	else {
	    fatal_error("In get_html: unknown type '$type'.\n");
	}
	# and now fetch this URL
	if ($type eq "ajax") {
	    fetch_http_ajax($Rhtml, $urldata, $timeout);
	} else {
	    fetch_http_get($Rhtml, $slashdot_url, $timeout);
	}
	# and store back into cache
	$prefs{enable_local_cache} && store_file_in_cache($Rhtml, $cache_fn);
    }

    if ($$Rhtml =~ m!AVANTSLASH_URL=(http://\S+)$!) { # url is appended to result data
	$fetch_info{url} = $1;
    }
    if ($$Rhtml =~ m!^([1-6][0-9][0-9] .{,200}?)\n! || $$Rhtml =~ m!<title>([345]\d\d .*?)</title>!) {
	$fetch_info{'statuscode'} = $1;
    }

    if ($type ne "ckupdate" && $type ne "rss") {
	correct_formatting($Rhtml);
    }
	 
    if ($prefs{"dump_reformatted_html"})
    {
	print_content_type_html();
	print $page;
	exit;
    }
}
	
# fetch URL over HTTP; store resulting raw html data in string ref.
# timeout in seconds
sub fetch_http_get 
{
    my ($Rhtml, $url, $timeout) = @_;
    
    my $ua = new LWP::UserAgent;
    $ua->agent($as_user_agent);
    # obsolete
    # $ua->default_header("Cookie" => "betagroup=-1"); # from http://slashdot.org/?nobeta=1

    my $req = new HTTP::Request GET => $url;
    # under certain (past?) conditions, slashdot would act weirdly without a referrer.
    if ($url =~ /slashdot.org/) {
	$req->header("Referer" => "https://slashdot.org/");
    }

    local $SIG{ALRM} = sub { fatal_error("TIMEOUT"); };
    alarm($timeout);
    $fetch_info{pagedate} = time(); # global variable
    my $res = $ua->request($req); # In case of timeout, result is "500 TIMEOUT".
    alarm(0);
    $$Rhtml = $res->content."\nAVANTSLASH_URL=$url\n";
}

# fetch AJAX data over HTTP, using POST method
# fetch URL over HTTP; store resulting raw html data in string ref.
sub fetch_http_ajax
{
    my ($Rhtml, $urldata) = @_;
    if ($urldata =~ m!([0-9]+),\s*([0-9]+)!) {
	my $cid = $1;
	my $sid = $2;
	# this gives only the date and comment text
	# "op=comments_fetch&cids=$cid&discussion_id=$sid&abbreviated=$cid,0&pieces=$cid";
	# this gives author/title/score as well, with much more html overhead.
	my $postdata = "op=comments_fetch&cids=$cid&discussion_id=$sid";
	my $ua = new LWP::UserAgent;
	$ua->agent($as_user_agent);
	my $req;
	my $req_url = "https://slashdot.org/ajax.pl";
	$req = new HTTP::Request(POST => $req_url);
	$req->content_type('application/x-www-form-urlencoded');
	$req->content($postdata);
	my $res = $ua->request($req);
	if ($res) {
	    $$Rhtml = $res->content."\nAVANTSLASH_URL=$req_url\n";
	    return;
	}
	# HTTP error
	print("Content-Type: text/plain\n\nAjax error: HTTP error\n");
	exit;
    } else {
	print("Content-Type: text/plain\n\nAjax error: Undefined cid/sid.\n");
	exit;
    }
}

# purge old files from cache.
# optional argument: wildcard filename and expiration age 
sub purge_cache
{
    my ($pattern, $maxage_force) = @_;
    if (!defined($pattern) || !defined($maxage_force)) {
	$pattern = "*";
	$maxage_force = 0;
    }
    my @files = glob("cache/$pattern");
    foreach my $thisfile (@files)  {
        my $age = (stat("$thisfile"))[9];
	my $max_age = ($maxage_force ? $maxage_force : $prefs{"cache_timeout"}) * ONE_MINUTE;
	if (!$maxage_force && $thisfile =~ m!^cache/([a-z]+)-! && defined($cache_life_min{$1})) {
	    $max_age = $cache_life_min{$1} * ONE_MINUTE;
	}
        unlink("$thisfile") if (time - $age > $max_age);
    }
}

# get specified file data from cache, if not expired. Return in string ref.
# also remove expired files from cache directory.
# if CGI parameter force_reload is set, act as if cache does not exist.
# return 1 on success.
sub get_file_from_cache
{
    my ($Rhtml, $filename) = @_;
    $filename =~ s!-?(\.html)?$!.html!; # just to be sure
    $fetch_info{cache} = $filename;

    # first remove old files from cache directory
    purge_cache();

    # force reload?
    if (cgi_param("force_reload")) {
	return 0;
    }
    
    # if the desired file is still in cache, grab it.
    $$Rhtml = "";
    if (-f "cache/$filename") {
	open(my $fh, "cache/$filename") || die "Can't open cache file $filename: $!";
	while(<$fh>) {
	    $$Rhtml .= $_;
	}
	$fetch_info{pagedate} = (stat($fh))[9];
	close $fh;
	$fetch_info{'cache'} .= ' [found]';
	return 1;
    }
    $fetch_info{'cache'} .= ' [not found]';

    return 0;
}


# speaks for itself
sub store_file_in_cache {
    my ($Rhtml, $filename) = @_;
    open(FILE, ">cache/$filename") || die "Can't write out to cache/$filename: $!";
    print FILE $$Rhtml;
    close FILE;
}


sub print_issue_links {
  # links to older issues
  my $issue = cgi_param("issue");
  if ($issue eq "") { $issue = ($prefs{'demo_mode'} ? 3 : -1); }
  print("<form method='GET' action='$self_url'>\n".
	"Older issues: <select name='issue' onchange='this.form.submit()'>\n");
  my $issue0 = $prefs{'demo_mode'} ? 3 : 0;
  foreach my $i ($issue0..$issue0+5) {
      my $selected =  ($i == $issue) ? " selected" : "";
      print(" <option value='$i'$selected>&nbsp;$i&nbsp;</option>\n");
  }
  print("</select></form>\n".
	"<form method='GET' action='$self_url'>\n");
  my $js = "document.getElementById('ymd').value=''";
  print(" days ago, or enter date:".
	"<input type='text' id='ymd' size='10' inputmode='digits' value='yyyymmdd' name='issuedate' onfocus=\"$js\">\n".
	"<input type='submit' value='Go'>\n".
	"</form>\n");
}

# generate css, with recursive includes  (@import 'filename.css')
sub generate_css
{
    # paranoia
    my $cssnames = sanitize_string_noslash($_[0]);
    # script timestamp also counts for timestamp
    chdir("css") || fatal_error("css/: $!\n");
    my $scriptname = $ENV{"SCRIPT_FILENAME"};
    my $tstamp_self = (-f $scriptname) ? (stat($scriptname))[9] : 0;
    my ($cssdata, $tstamp) = generate_css_recursive($cssnames, 5, $tstamp_self);
    print("Content-Type: text/css\n");
    print("Last-Modified: ".strftime("%a, %d %b %Y %T GMT", gmtime($tstamp)), "\n");
    print("Cache-control: max-age=".$cache_life_min{'css'}*ONE_MINUTE."\n");
    print("\n", $cssdata);
    chdir("..");
}


# read CSS recursively;
# filenames can be single file or comma-separated list (.css extension optional)
# return ($cssdata, $newest_timestamp)
sub generate_css_recursive
{
    my ($fnames, $recur_level, $tstamp) = (@_);
    my $cssdata = "";
    foreach my $fname (split(/,/, $fnames)) {
	($fname eq "") && next;
	if ($fname !~ /css$/) {
	    $fname .= ".css";
	}
	if (! -f $fname) {
	    $cssdata .= "/* ERROR: $fname: no such file */\n";
	    next;
	}
	open(my $fh, "$fname") || fatal_error("$fname: $!\n");
	while (<$fh>) {
	    if (/^\s*\@import\s+[\"\'](.*)[\"\']/) {
		my $inc_fname = $1;
		($recur_level <= 0) && fatal_error("$fname including $inc_fname: too many recursion levels.\n");
		my $inc_data;
		($inc_data, $tstamp) = generate_css_recursive($inc_fname, $recur_level - 1, $tstamp);
		$cssdata .= $inc_data;
		next;
	    }
	    else {
		# remove redundant characters
		s!/\*.*\*/!!g;
		m!^\s*$! && next;
		s!^\s+!!;
		$cssdata .= $_;
	    }
	}
	my $this_tstamp = (stat($fh))[9];
	if ($this_tstamp > $tstamp) {
	    $tstamp = $this_tstamp;
	}
	close($fh);
    }
    return ($cssdata, $tstamp);
}

sub print_ckupdate_js
{
    if ($prefs{check_updates}) {
	print("<script type=\"text/javascript\" src=\"$self_url?ckupdate=2\"></script>\n");
    }
}

sub print_ckupdate_link
{
    my $pagetype = shift;
    my $reload_url = $ENV{'REQUEST_URI'};
    if ($reload_url !~ /force_reload=1/) {
	$reload_url .= (($reload_url =~ /\?/ ? '&' : '?') . 'force_reload=1');
    }
    $reload_url =~ s/\&dummy=\d+//g;
    $reload_url .= '&dummy='.int(rand(10000));

    print("<div class='error'>\n".
	  "Could not find items on the $pagetype; either there are none, or the server's HTML code changed.\n".
	  "Possibly, your site's IP was barred from the server.<br>\n".
	  "<button type='button' onclick='document.location.href=\"$self_url?ckupdate=1\"'>Check for updates</button>\n".
	  "<button type='button' onclick='document.location.href=\"$reload_url\"'>Reload</button>\n".
	  "</div>\n");
}


# get statistics on cache
sub show_cache_status {
    # count files by prefix, statistics on oldest and size
    my @flist = glob("cache/*[-.]*");
    my %pcount;
    my %poldest;
    my %psize;
    my $tm_now = time();
    foreach my $fn (@flist) {
	($fn !~ m!/(.*?)[-.]!) && next;
	my $prefix = $1;
	if (!defined($pcount{$prefix})) {
	    $pcount{$prefix} = 0;
	    $poldest{$prefix} = $tm_now;
	    $psize{$prefix} = 0;
	}
	++$pcount{$prefix};
	my $tstamp = (stat($fn))[9];
	if ($tstamp < $poldest{$prefix}) { $poldest{$prefix} = $tstamp; }
	$psize{$prefix} += (stat($fn))[7];
    }
    # dump results
    print("<table class='stats'><tr><th>Type <th>Count <th>Size <th>Oldest <th>MaxAge\n");
    foreach my $prefix (sort { $a cmp $b } keys(%pcount)) {
	# oldest age in human-readible form
	my $oldest = format_time_interval($tm_now - $poldest{$prefix}, 1);

	# max age
	my $maxage = (defined($cache_life_min{$prefix})) ? $cache_life_min{$prefix} : $prefs{'cache_timeout'};
	$maxage = format_time_interval($maxage * ONE_MINUTE, 1);

	# output
	printf("<tr><td>%s <td>%d <td>%.0f kB <td>%s <td>%s\n",
	       $prefix, $pcount{$prefix}, $psize{$prefix}/1024, $oldest, $maxage);
	
    }
    print("</table>\n");
}


# format time interval in human-readible form
# arguments: time in seconds, abbrev flag
# return: string
sub format_time_interval {
    my $ago = shift;
    my $abbrev = shift;
    my $agounit;
    my $plural = "";

    my @tmsplit = gmtime($ago);
    my ($secs, $mins, $hrs) = ($tmsplit[0], $tmsplit[1], $tmsplit[2]);
    if ($ago < 60) {
	$plural = ($ago > 1 ? "s" : "");
	return "$ago sec".($abbrev ? "" : "ond$plural");
    }
    if ($ago < 600) {
	$plural = ($mins > 1 ? "s" : "");
	$secs = sprintf("%02d", $secs);
	return "$mins:$secs min".($abbrev ? "" : "ute$plural");
    }
    if ($ago < 3600) {
	return "$mins min".($abbrev ? "" : "utes");
    }
    if ($ago < 86400) {
	$plural = ($hrs > 1 ? "s" : "");
	$mins = sprintf("%02d", $mins);
	return "$hrs:$mins h".($abbrev ? "" : "our$plural");
    }
    return sprintf("%.1f days", $ago/86400);
}


sub search_form {
    my $query = shift;
    return "<form method='GET' action='$self_url'>\n".
	"<input type='text' size=15 name='search' value='$query'>\n".
	"<input type='submit' value='Search'>\n".
	"</form>\n";
}

# set css cookie, using CGI parameters 'base' and multiple 'mod'
# special case: base=reset
sub set_css_cookie()
{
    my $basecss = cgi_param('base');
    my $modcss = join(",", CGI::param('mod')); # must use CGI::param since it's a list
    # construct cookie
    my $exptime = ($basecss eq "reset") ? 60 : time() + 86400*365*10;
    my $cookie_exp = strftime("%a, %d %b %Y %T GMT", gmtime($exptime));
    my $cssval = "$basecss,$modcss";
    $cssval =~ s!,+$!!;
    $cssval = uri_escape($cssval); # commas may be interpreted as separator
    
    # find out referring URL
    my $refer_url = cgi_param("referer");
    my $dum = int(rand(10000));
    my $redir_url;
    if (cgi_param("return") eq "") {
	$redir_url = "//" . $ENV{HTTP_HOST} . "$self_url?showprefs=1&dum=$dum&referer=$refer_url";
    } else {
	if ($refer_url ne "") {	
	    $redir_url = $refer_url . (($refer_url =~ m!\?!) ? "&" : "?") . "dum=$dum";
	} else {
	    $redir_url = "//" . $ENV{HTTP_HOST} . $self_url;
	}
	
    }
    print("Status: 302 moved\n");
    print("Location: $redir_url\n");
    print("Set-Cookie: css=$cssval; Expires=$cookie_exp\n");
    print_content_type_html();
    print("Go to <a href='$redir_url'>$redir_url</a>\n");
}


# get user agent from enviroment, or from ua= CGI parameter
sub get_UA {
    (cgi_param("ua") ne "") && return cgi_param("ua");
    return getenv('HTTP_USER_AGENT');
}

# check for abuse in demo mode.
sub demo_sanity_check
{
    #### HTTP referer
    # everything except the main page should have this script as the referrer
    if (cgi_param('issue') || cgi_param('comments') || cgi_param('ajax') || cgi_param('setcss') ||
	cgi_param('showcredits') || cgi_param('ckupdate') || cgi_param('showprefs')) {
	my $ref = $ENV{'HTTP_REFERER'};
	my $selfref = "$ENV{'HTTP_HOST'}$self_url";
	$selfref =~ s!/[^/*]$!!;  # self url without index.cgi?... or avantify.cgi?... part
	($ref ne "" && $ref !~ m!^https?://$selfref!) &&
	    fatal_error("External linking to this page is not allowed.\n");
    }
    #### restrict queries per remote address
    # store number of queries as file length in cache directory. 
    my $maxqueries = 50;
    my $client = $ENV{'REMOTE_ADDR'};
    if (!$client) { $client = "0000"; }
    $client = sanitize_string_noslash($client);
    my  $cachefn = "democalls-$client.html";
    my $cachedata = "";
    my $exists = get_file_from_cache(\$cachedata, $cachefn);
    ($exists && length($cachedata) > $maxqueries) &&
	fatal_error("Daily limit reached for this AvantSlash demo.");
    # didn't crash yet? Append one character to file
    my $fh;
    open($fh, ">>cache/$cachefn") || fatal_error("$cachefn: $!\n"); 
    print($fh ".");
    close($fh);
}

# arg1: message
sub fatal_error {
    my $msg = shift;
    print("Status: 500 Server error\n".
	  "Content-Type: text/html\n\n".
	  "<html><head><title>Error</title><body>\n".
	  "<h1>Error</h1>\n".
	  "<p><b>$msg</b>\n".
	  "<p>Maybe you want to go to the ".
	  "<a href=\"$self_url\">AvantSlash main page</a> on this server.\n".
	  "</body></html>\n");
    exit;
}

# setup TZOFFS (in %prefs); set server timezone to Slashdot timezone.
sub set_tzoffset
{
    my $tm_now = time();
    if ($prefs{'timezone'} ne "auto") {
	$ENV{'TZ'} = $prefs{'timezone'};
    }
    # convert 'now' to desired time display format 
    tzset();
    my @loctm = localtime($tm_now);
    $prefs{'time_fmt'} =~ s!%Z!strftime('%Z', @loctm)!ge;
    $prefs{'time_fmt'} =~ s!%z!strftime('%z', @loctm)!ge;
    $loctm[8]=0; # pretend that there is no summer time

    # convert 'now' to Slashdot time format
    $ENV{'TZ'} = 'America/New_York';
    tzset();
    my @sdtm = localtime($tm_now);
    $sdtm[8]=0; # pretend that there is no summer time

    # how much to add to slashdot time to make it local time
    $prefs{'tzoffset'} = mktime(@loctm) - mktime(@sdtm);

    # adjust time format %Z

}

# takes a 'slashdot' time string, e.g.
# 'Friday March 20, @01:58AM' or 'Friday March 20 2010, @01:58AM'
# 'Wednesday May 08, 2013 @02:12AM'
#
# soylent format: 'Sunday February 23, @01:00PM &nbsp;'
# and convert it to local time representation
sub reformat_time
{
    my $tstring = shift;
    my ($mday, $mname, $year, $h, $m, $apm);
    #                  DoW   Month   DoM   , Year         HH  : MM   AM/PM
    if ($tstring =~ m!^\S+\s+(\S+)\s+(\d+)(,\s+(\d+))? \@(\d+):(\d+)([AP])M!) {
	($mname, $mday, $year, $h, $m, $apm) = ($1, $2, $4, $5, $6, $7);
	if ($h == 12) { $h = 0; }
	$apm = ($apm eq 'P') ? 12*3600 : 0;
    # soylent has the comma before year even if there is no year
    } elsif ($tstring =~ m!^\S+\s+(\S+)\s+(\d+),(\s+(\d+))? \@(\d+):(\d+)([AP])M!) {
	($mname, $mday, $year, $h, $m, $apm) = ($1, $2, $4, $5, $6, $7);
	if ($h == 12) { $h = 0; }
	$apm = ($apm eq 'P') ? 12*3600 : 0;
    } else {
	# could not parse; return unchanged.
	return "[$tstring]";
    }
    my %mnames = qw(January 0 February 1 March 2 April 3
                    May 4 June 5 July 6 August 7 September 8
                    October 9 November 10 December 11);
    my $mnum = $mnames{$mname};
    # Slashdot only displays (used to display?) the year if it's longer than 6 months ago.
    # Deal with that.
    if (!defined($year)) {
	my @loctm = localtime();
	$year = ($mnum > $loctm[4]) ? $loctm[5]-1 : $loctm[5];
    } else {
	$year -= 1900;
    }
    #  0    1    2     3     4    5     6     7     8
    #($sec,$min,$hour,$mday,$mon,$year,$wday,$yday,$isdst)
    my @tdata = (0, $m, $h, $mday, $mnum, $year, 0, 0, -1);
    my $tm = mktime(@tdata) + $prefs{tzoffset} + $apm;
    return strftime($prefs{'time_fmt'}, localtime($tm));
}


# print (arg 1) or return (arg 0) status information ('500 error' etc.) from %fetch_info
sub status_message {
    my $print_flag = shift;
    if ($fetch_info{'statuscode'} ne 'undef') {
	my $html = "<div class='error'>Note: slashdot server issue; $fetch_info{statuscode}</div>\n";
	if ($print_flag) { print($html); }
	else { return $html; }
    }
    return "";
}

# argument: new version
sub run_upgrade {
    my $tver = shift;
    ($tver !~ /^\d+\.\d+/) && fatal_error("Version '$tver' invalid.\n");
    ($ENV{'REQUEST_METHOD'} ne "POST") && fatal_error("Only available via POST method.");
    (! -f "autoupgrade.sh") && fatal_error("autoupgrade.sh not found - upgrade disabled.\n");
    my $cmd = "sh autoupgrade.sh '$tver'";
    open(my $fh, "$cmd |") || fatal_error("Error executing $cmd .");
    
    print("Content-type: text/plain\n\n");
    print("--Upgrading avantslash to version $tver--\n");
    while (<$fh>) {
	print($_);
    }
    exit(0);
}

# print "content-type: text/html" header with charset, with double newline.
# both slashdot and soylent use nominally utf-8.
sub print_content_type_html {
    print("Content-Type: text/html; charset=utf-8\n\n");
}
