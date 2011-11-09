% - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
%
% Splash screen (hidden-timeout mode).
%
% - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


% - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
% Create new splash window.
%
% ( ) ==> ( window )
%
/window.splash {
  widget.size array
  dup .type t_splash put
  dup .font font.normal put
  dup .ed.font font.normal put
  dup .color.fg boot.text.normal put
} def


% - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
% Initialize splash window.
%
% ( window ) ==> ( )
%
/splash.init {
  pop
} def


% - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
% Draw splash window.
%
% ( window ) ==> ( )
%
/splash.show {
  window.push

  menu.init
  % like 'menu.entry true MenuSelect', but without drawing on the screen
  bootoptions.init

} def


% - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
% Handle keyboard input.
%
% ( key_in ) ==> ( key_out )
%
/splash.input {
  /timeout.hidden false def
  "splash.pcx" findfile setimage
  0 0 image.size image
%  0 0 moveto background.file setimage 0 0 image.size image
  window.done
  window.main
  dup window.init
      window.show
  lang.displayed not { panel.lang } if
  pop 0
} def
