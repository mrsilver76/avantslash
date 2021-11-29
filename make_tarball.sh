
FILELIST="
  README.1ST
  config.dist
  avantify.config
  cache/
  copyright-avantslash.txt
  demo-info.txt
  expandmsg.js
  expandmsg_soylent.js
  avantify.cgi
  index.cgi
  make_tarball.sh
  autoupgrade-disabled.sh
  diagnostics.cgi
  doc/licence.txt
  doc/readme.txt
  doc/changelog.txt
  doc/debugging.txt
  
  css_dist.txt
  css/base.icss
  css/dark.css
  css/invert.css
  css/mini_slashdot.icss
  css/mini_slashdot.css
  css/soylent.icss
  css/soylent.css
  css/soy-inv.css
  css/soy-dark.css
  css/desktop_slashdot.css
  css/bare.css
  css/italquote.css
  css/noindent.css
  css/noitalic.css
  css/noshade.css
  css/noscroll.css
  css/bigbutton.css
  css/font-l.css
  css/font-s.css
  css/font-xs.css
  css/serif.css


  authenticate/login.html
  authenticate/.htaccess
  authenticate/readme.txt
  
  logo40g.png
  logo40w.png
  logo40b.png
  logo40by.png
  logo40Sw.png
  logo40Sb.png
  logo40Sby.png
  apple-touch-icon-ipad.png
  apple-touch-icon-iphone4.png
  apple-touch-icon-iphone.png
  favicon.ico
  " # closing quote

TARFILE=tarball/avantslash-`date +%Y%m%d`.tar.gz
# ZIPFILE=tarball/avantslash-`date +%Y%m%d`.zip

# note: content of cache directory should not be archived.

tar --no-recursion -czf $TARFILE $FILELIST "$@"
echo $TARFILE

# # prevent updating existing zipfile in case of deleted files
# [ -f $ZIPFILE ] && rm $ZIPFILE
# zip -9q $ZIPFILE $FILELIST "$@"
# echo $ZIPFILE
 

