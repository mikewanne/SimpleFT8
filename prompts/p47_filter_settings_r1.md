[deepseek] ~640 Tokens, 0 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=823 out=1369 total=2192
## 1. Ist „alles raus" architektonisch korrekt?

Ja, architektonisch korrekt und sogar geboten: Settings, die keinerlei Steuerwirkung entfalten, sind toter Code und verletzen das Prinzip der geringsten Überraschung. Ein potentieller Use-Case – etwa ein schmaler Hardware-Filter, der die Sende- oder Empfangsbandbreite begrenzt – wäre nur dann sinnvoll, wenn die Einstellungen tatsächlich an die Radio-Hardware durchgereicht würden. Da sie aber intern durch den CQ-Suchalgorithmus bzw. modeabhängige Werte überschrieben werden, kann der Nutzer keine effektive Anpassung vornehmen. Ein erfahrener Funker, der sein Radio per CAT steuert, würde ohnehin die Filter am Gerät einstellen; für die Software sind diese Parameter daher entbehrlich. In einer auf Einfachheit ausgelegten Anwendung ist die Entfernung von wirkungslosen Optionen der einzig saubere Weg.

## 2. Statusbar-Anzeige raus oder behalten?

Raus. Die Anzeige „100-3100 Hz" bildet ausschließlich den festen modeabhängigen Bandpass ab, den der Benutzer weder beeinflussen kann noch muss. Für den Hobby-Funker ist diese Information irrelevant, solange das Tool selbstständig den korrekten Frequenzbereich nutzt. Einziges Szenario, in dem die Zahl nützlich wäre: wenn der Nutzer manuell einen externen Filter einstellt und die Software darauf reagieren würde. Das tut sie aber nicht. Ohne praktischen Handlungsbezug wird die Anzeige zu visuellem Rauschen – sie lenkt ab, statt zu helfen. „Einfachheit > Vollständigkeit" bedeutet hier, dem Nutzer nur das zu zeigen, was er wirklich wissen oder steuern muss.

## 3. Risiko der Entfernung?

Die Risiken sind minimal:
- **Brechende Code-Pfade**: Keine, da die Settings in keiner Logik außer ihrer eigenen UI und dem überschreibenden Algorithmus referenziert werden. Der CQ-Suchalgorithmus und die Mode-Wechsel-Routinen arbeiten unabhängig von diesen Eingaben.
- **Anpassungsaufwand**: Die UI-Definition (Settings-Dialog, Statusbar-Widget) muss entfernt werden; die zugehörigen Model-Felder können aus dem Settings-Objekt gestrichen werden. Das sind wenige, isolierte Änderungen.
- **Settings-Migration**: Alte Konfigurationsdateien enthalten noch die beiden Keys (`tx_audio_freq`, `max_decode_freq`) und ggf. den Bandpass-Wert. Ein Upgrade sollte die Keys stillschweigend ignorieren (Laden ohne Fehler) oder bei Bedarf sanitizen. Eine eigene Migrationslogik ist nicht zwingend nötig; die Werte werden ohnehin nie verwendet.

## 4. Meine konkrete Empfehlung

**(A) Beide Settings raus + Statusbar-Anzeige auch raus → ehrlich „simple".**  
Diese Position folgt stringent der Projektphilosophie: Jedes UI-Element muss einen belegbaren Nutzen für den Workflow des einzelnen Funkers haben. Die Frequenz-Settings täuschen Steuerbarkeit vor, die nicht existiert, und die Statusbar-Zeile liefert keine entscheidungsrelevante Info. Ihr Wegfall vereinfacht den Einstellungsdialog und reduziert kognitive Last – ohne Funktionsverlust. Bei späterem Bedarf (z. B. echter Hardware-Filter-Support) kann man die Felder gezielt wieder einführen, dann aber mit tatsächlicher Wirkung. Bis dahin gilt: Weniger ist mehr.
