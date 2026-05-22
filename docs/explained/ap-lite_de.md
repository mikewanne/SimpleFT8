# AP-Lite — A-Priori-Rettung schwacher QSOs

## Kurz gesagt

Wenn der QSO-Partner zu schwach zum Dekodieren ist, rät AP-Lite die wenigen
möglichen Nachrichten und prüft, welche davon zum Empfang passt. „AP" steht
für *a priori* — im Voraus bekannt.

## Die Idee

Mitten in einem QSO ist fast alles schon bekannt: beide Rufzeichen und der
Ablauf. Offen sind nur wenige Varianten:

- Du wartest auf den Rapport → eine Handvoll Zahlenwerte.
- Du wartest auf die Bestätigung → genau drei: `RR73`, `RRR` oder `73`.

Schafft der Decoder den Partner-Slot nicht, erzeugt AP-Lite für jede dieser
wenigen Varianten das FT8-Referenzsignal und vergleicht es mit dem Empfang.
Passt eine Variante klar besser als alle anderen, gilt sie als erkannt.

## Wie der Vergleich funktioniert

AP-Lite entschlüsselt nichts von Grund auf und kombiniert auch keine Slots.
Es nutzt zwei Kniffe:

1. **Phasen-unabhängiger Vergleich.** Empfang und Kandidat werden so
   korreliert, dass es egal ist, wie die Trägerphase gerade liegt — der
   Vergleich bleibt stabil.
2. **Kleiner Frequenz-Suchlauf.** Reale Stationen liegen oft ein paar Hertz
   neben der erwarteten Frequenz; AP-Lite sucht dieses Fenster ab.

## Die Entscheidung — der Margen-Test

Statt einer festen Schwelle prüft AP-Lite den *Abstand*: Der beste Kandidat
muss den zweitbesten deutlich schlagen.

- echte Nachricht vorhanden → klarer Abstand
- nur Rauschen oder ein fremdes Signal → praktisch kein Abstand

Dieser relative Test ist robust — er funktioniert auch dann, wenn das Signal
so schwach ist, dass der absolute Vergleichswert klein bleibt.

## Was AP-Lite NICHT tut

AP-Lite ist rein **beratend**. Bei einem Treffer zeigt die App eine
Info-Zeile im QSO-Fenster — mehr nicht. Es loggt kein QSO automatisch und
löst kein Senden aus. Der Operator entscheidet. Darum kann AP-Lite kein QSO
„erfinden", das es nie gab.

## Nutzen

AP-Lite hilft in einem schmalen Bereich am unteren Rand: wenn das
Partner-Signal *knapp* zu schwach für den normalen Decoder ist. Der Gewinn
sind ein paar dB „Abschluss-Sicherheit" — marginale QSOs, die sonst in den
Timeout laufen würden. Am meisten zahlt sich das im Diversity-DX-Modus aus,
wo man bewusst schwache Stationen arbeitet.

## Zähler in der Statusleiste

Unten in der App steht `AP = (x)`. Das x ist die Zahl der QSOs, bei denen
AP-Lite eine Nachricht erkannt hat. Der Zähler wird gespeichert und läuft
über App-Neustarts hinweg weiter — gedacht zur Beobachtung im Feld.

## Status

Aktiv. AP-Lite ist ein beratendes Feature und greift nicht in den
QSO-Ablauf ein.
