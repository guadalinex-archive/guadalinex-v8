// use ubuntu plugin finder service
pref ("pfs.datasource.url", "http://people.ubuntu.com/~asac/cgi-bin/plugin-finder.py?mimetype=%PLUGIN_MIMETYPE%&appID=%APP_ID%&appVersion=%APP_VERSION%&clientOS=%CLIENT_OS%&chromeLocale=%CHROME_LOCALE%");
// See http://kb.mozillazine.org/Localize_extension_descriptions
pref("extensions.guadafox@guadalinex.org.description", "chrome://guadafox/locale/guadafox.properties");


// intl-property fixes
pref("general.useragent.locale", "chrome://global/locale/intl.properties");
pref("general.useragent.contentlocale", "chrome://browser-region/locale/region.properties");
pref("intl.accept_languages",               "chrome://global/locale/intl.properties");
pref("intl.collationOption",                "chrome://global-platform/locale/intl.properties");
pref("intl.menuitems.alwaysappendaccesskeys","chrome://global/locale/intl.properties");
pref("intl.menuitems.insertseparatorbeforeaccesskeys","chrome://global/locale/intl.properties");
pref("intl.charsetmenu.browser.static",     "chrome://global/locale/intl.properties");
pref("intl.charsetmenu.browser.more1",      "chrome://global/locale/intl.properties");
pref("intl.charsetmenu.browser.more2",      "chrome://global/locale/intl.properties");
pref("intl.charsetmenu.browser.more3",      "chrome://global/locale/intl.properties");
pref("intl.charsetmenu.browser.more4",      "chrome://global/locale/intl.properties");
pref("intl.charsetmenu.browser.more5",      "chrome://global/locale/intl.properties");
pref("intl.charsetmenu.browser.unicode",    "chrome://global/locale/intl.properties");
pref("intl.charsetmenu.mailedit",           "chrome://global/locale/intl.properties");
pref("intl.charset.detector",               "chrome://global/locale/intl.properties");
pref("intl.charset.default",                "chrome://global-platform/locale/intl.properties");
pref("intl.content.langcode",               "chrome://browser-region/locale/region.properties");
pref("font.language.group",                 "chrome://global/locale/intl.properties");


// ubuntu-printing overwrites
pref("print.print_command", "lpr ${MOZ_PRINTER_NAME:+-P\"$MOZ_PRINTER_NAME\"}");
pref("print.postscript.print_command", "lpr ${MOZ_PRINTER_NAME:+-P\"$MOZ_PRINTER_NAME\"}");


// look-and-feel modifications in firefox-branding.js
pref("startup.homepage_override_url","chrome://guadafox/locale/guadafox.properties");
pref("startup.homepage_welcome_url","chrome://guadafox/locale/guadafox.properties");
pref("app.update.url.details","chrome://guadafox/locale/guadafox.properties");

// look-and-feel modifications in firefox.js
pref("browser.startup.homepage","chrome://guadafox/locale/guadafox.properties");
pref("app.releaseNotesURL","chrome://guadafox/locale/guadafox.properties");
pref("browser.throbber.url","chrome://guadafox/locale/guadafox.properties");

pref("browser.link.open_newwindow", 3);
pref("browser.link.open_external", 3);
pref("middlemouse.contentLoadURL", false); // setting to false disables pasting urls on to the page
pref("bidi.browser.ui", true);
pref("browser.startup.homepage_override.mstone","ignore");


// look-and-feel modifications in all.js
// pref("dom.event.contextmenu.enabled",       false);
pref("font.default.el", "sans-serif");
pref("font.default.th", "sans-serif");

pref("font.default.tr", "sans-serif");
pref("font.default.el", "sans-serif");
pref("font.default.th", "sans-serif");
pref("font.default.tr", "sans-serif");
pref("font.default.el", "sans-serif");
pref("font.default.th", "sans-serif");
pref("font.default.tr", "sans-serif");
pref("font.default.el", "sans-serif");
pref("font.default.th", "sans-serif");
pref("font.default.tr", "sans-serif");
pref("font.default.el", "sans-serif");
pref("font.default.th", "sans-serif");
pref("font.default.tr", "sans-serif");


// disable-default-browser-check on startup by defaullt
pref("browser.shell.checkDefaultBrowser", false);


// locale-by-match-os
pref("intl.locale.matchOS", true);

// kerberos-for-https
pref("network.negotiate-auth.trusted-uris", "https://");

//ed2k support
pref("network.protocol-handler.external.ed2k",true);
pref("network.protocol-handler.warn-external.ed2k", false);
pref("network.protocol-handler.expose.ed2k", false);
