how to configure (arch or arch-based distro):

1) run evtest
2) get your device name (exact name)

```
...
/dev/input/event4:	ELAN06FA:00 04F3:327E Touchpad
/dev/input/event5:	KTMicro KT USB Audio Consumer Control
/dev/input/event6:	KTMicro KT USB Audio
/dev/input/event7:	SINO WEALTH Trust GXT 871 ZORA
/dev/input/event8:	SINO WEALTH Trust GXT 871 ZORA Keyboard
/dev/input/event9:	Video Bus
```
for ex, it's `SINO WEALTH Trust GXT 871 ZORA` for me:

3) edit `mechanical-keyboard-debounce.service` with your keyboard name (l.21)
4) run makepkg -si

goodbye multiple inputs in a few ms :]