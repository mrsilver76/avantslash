AvantSlash
Copyright (c) Richard Lawrence and Han-Kwang Nienhuys 2000-2015
Released under the GNU GPL.

Abstract
--------

AvantSlash allows you to read Slashdot on a smartphone with minimal
data, CPU, and memory usage. This is in contrast with the standard
slashdot pages (including their 2013 mobile site) that will require a
beefy device and a large data connection.

AvantSlash takes the bloated pages from slashdot.org, runs them though
some perl, and outputs mobile-friendly content.

Licence
-------

This is released under the GNU GPL. You can find more details about
that in the file "LICENCE". In short: (1) you can do what you want
with this as long as if you redistribute it, you use the same licence,
and (2) there is no warranty.

System requirements
-------------------

You need a web server with Perl version 5 or greater plus the CGI and
LWP packages. 

Installation for Slashdot
-------------------------

Create a directory that is accessible over HTTP and unpack the tar.gz
file there. You can then access the script as avantify.cgi in that
directory, for example http://www.example.com/avantslash/avantify.cgi.

If it doesn't work, try to run the diagnostics.cgi script over HTTP
for common issues. If that results in a server error as well, you will
have to check the server error log. Issues could be:

* No execute permissions on the CGI scripts (can result from an FTP
  file transfer).  Use "chmod 755 *.cgi" (without quotes) to make the
  CGI scripts executable.

* The web server is not configured to run CGI scripts. On an
  Apache-based web server, this is typically enabled using "Options
  +ExecCGI" and "AddHandler cgi-script .cgi" in a .htaccess and/or
  server configuration file. For servers that require CGI scripts to
  be in the /cgi-bin directory, the path to the configuration files
  needs to be edited.

You may wish to protect your AvantSlash installation against
unauthorized use; you probably don't want your site to be found by
Google. In the directory authenticate/ you can find an example
.htaccess and login.html. 

Installation for SoylentNews
----------------------------

If you want to use AvantSlash to view stories from SoylentNews.org, it
works the same as above, but you have to install it in a separate
directory and set the parameter "SOYLENT 1" in your config.local file.
Probably you will also want to set "DEFAULT_STYLESHEET soylent" and
"THRESHOLD 2". 


Customisation
-------------

AvantSlash can be customised to your viewing preferences and this is
achieved in one of two ways. If you want to change the way the page
looks then you can can do this from the "About/Preferences" page which
will allow you to modify the way the pages render on a per-device
basis - this means that it could be different for your smartphone and
for your tablet. 

The second way is through the use of a plain text configuration file that
resides in the same location as the avantify.cgi script. It is called
"config.dist"; those preferences are applied across all
devices. Customizations should go in "config.local" to prevent them
from being overwritten if you update to a newer version of
Avantslash.

Auto-upgrading
--------------

If a file named 'autoupgrade.sh' is present in the avantslash
directory, the avantify.cgi script can execute this script, at
explicit user request, if a new version is available. The avantslash
distribution includes an example script
"autoupgrade-disabled.sh". Rename this script to "autoupgrade.sh" in
order to enable auto-upgrading. If your site requires additional
tweaks (e.g. setting directory permissions or installing to /cgi-bin),
you can make changes as needed; it will not be overwritten on
upgrades.

I added this feature because the server logs of avantslash.org
indicate that users tend to postpone upgrading to a new version for
several weeks or months. This makes upgrading easier, but of course
it's up to you whether you're comfortable with this feature, which can
be executed by any user of your avantslash site. Note that AvantSlash
needs upgrades every now and then if the HTML template used by the
slashdot or soylentnews site changes enough to break. 

How it works: if a new version of Avantslash becomes available, you
will see the familiar notification at the bottom of the page. Follow
the "What's new" link, which will show a button to initiate the
upgrade. You can still choose not to click that button.

Tracking
--------

AvantSlash will automatically check for updates and inform you if a
new release is available. When checking for updates, it will send some
information to the avantslash server for statistical purposes. More
precisely, it will send your current version number, user agent, and
style settings. If you don't like it, disable update checking or
change the code.

Contact
-------
Patches and feature requests are welcome.
Email feedback to avantslash-dev (at) avantslash (dot) org.

Contents last updated: 2015-07-13

