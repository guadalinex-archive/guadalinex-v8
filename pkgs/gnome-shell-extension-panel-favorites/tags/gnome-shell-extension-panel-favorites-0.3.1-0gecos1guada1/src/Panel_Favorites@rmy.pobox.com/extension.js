// Copyright (C) 2011 R M Yorston
// Licence: GPLv2+

const Gio = imports.gi.Gio;
const Lang = imports.lang;
const Shell = imports.gi.Shell;
const St = imports.gi.St;

const Gettext = imports.gettext;
const _ = Gettext.domain('gnome-shell').gettext;

const AppFavorites = imports.ui.appFavorites;
const Main = imports.ui.main;

const OVERVIEW_BUTTON_ICON_SIZE = 22;


let _f = null;


/**
 * Get an ApplicationInfo object.
 * The AppSystem API was changed in GnomeShell 3.1.90.1
 */
function lookupApp(appId) {
    if (Shell.AppSystem.get_default().lookup_app)
        return Shell.AppSystem.get_default().lookup_app(appId);
    else
        return Shell.AppSystem.get_default().get_app(appId);
}

function PanelLauncher(app) {
    this._init(app);
}

PanelLauncher.prototype = {
    _init: function(app) {
        this.actor = new St.Button({ name: 'panelLauncher',
                                    reactive: true });
        let icon = app.create_icon_texture(24);
        this.actor.set_child(icon);
        this.actor._delegate = this;
        let text = app.get_name();
        if ( app.get_description() ) {
            text += '\n' + app.get_description();
        }
        this.actor.set_tooltip_text(text);
        this._app = app;
        this.actor.connect('clicked', Lang.bind(this, function() {
            this._app.open_new_window(-1);
        }));
    }
};

function OverviewLauncher() {
    this._init();
}

OverviewLauncher.prototype = {
    _init: function() {
        this.actor = new St.Button({ name: 'panelLauncher',
                                    reactive: true });
        this._icon = new St.Icon({
            icon_name: 'view-fullscreen',
            icon_type: St.IconType.FULLCOLOR,
            icon_size: OVERVIEW_BUTTON_ICON_SIZE,
            style_class: 'system-status-icon'
        });

        this.actor.set_child(this._icon);

        let text = _f('Overview') + '\n' + _f('Overview workspace.');
        this.actor.set_tooltip_text(text);

        this.actor.connect('clicked', Lang.bind(this, function() {
            Main.overview.toggle();
        }));
    }
};

function PanelFavorites(path) {
    this._init(path);
}

PanelFavorites.prototype = {
    _init: function(path) {
        this._path = path;
        this.actor = new St.BoxLayout({ name: 'panelFavorites',
                                         style_class: 'panel-favorites' });

        this._display();

        Shell.AppSystem.get_default().connect('installed-changed', Lang.bind(this, this._redisplay));
        AppFavorites.getAppFavorites().connect('changed', Lang.bind(this, this._redisplay));

        let themeContext = St.ThemeContext.get_for_stage(global.stage);
        themeContext.connect('changed', Lang.bind(this, this._themeChanged));
    },

    _redisplay: function() {
        for ( let i=0; i<this._buttons.length; ++i ) {
            this._buttons[i].actor.destroy();
        }

        this._display();
    },

    _display: function() {
        let shellSettings = new Gio.Settings({ schema: 'org.gnome.shell' });
        let launchers = shellSettings.get_strv('favorite-apps');

        this._buttons = [];

        this._buttons.push(new OverviewLauncher());
        this.actor.add(this._buttons[0].actor);

        let j = 1;
        for ( let i=0; i<launchers.length; ++i ) {
            let app = lookupApp(launchers[i]);

            if ( app == null ) {
                continue;
            }

            this._buttons[j] = new PanelLauncher(app);
            this.actor.add(this._buttons[j].actor);
            ++j;
        }
    },

    _themeChanged: function(themeContext) {
        let theme = themeContext.get_theme();
        let dir = Gio.file_new_for_path(this._path);
        let stylesheetFile = dir.get_child('stylesheet.css');
        if (stylesheetFile.query_exists(null)) {
            theme.load_stylesheet(stylesheetFile.get_path());
        }
    }
};

function main(meta) {

    let localePath = meta.path + '/locale';
    Gettext.bindtextdomain('panel-favorites', localePath);
    _f = Gettext.domain('panel-favorites').gettext;

    let panelFavorites = new PanelFavorites(meta.path);
    Main.panel._leftBox.insert_actor(panelFavorites.actor, 1);
}

function init(meta) {
    main(meta);
}

function enable() {
}

function disable() {
}
