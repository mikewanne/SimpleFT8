# Slot-Lückenliste (Stand 2026-05-01)

Pro (Berlin-Stunde, Band, Modus) erfasst: Anzahl unique Tage mit Daten.
Berlin = UTC+2 (Sommerzeit). Bänder: 40m/30m/20m FT8 nur (Statistik-Filter v0.63).
Modi: Normal / Diversity Std / Diversity DX.

**Ziel:** 5 Tage flächendeckend pro Slot (siehe `feedback_statistics_strategy.md`).

---

## Verteilung

| Tage | Slots | Anteil | Status |
|---|---|---|---|
| 0 | 56 | 26 % | komplett leer (alle 30m) |
| 1 | 37 | 17 % | dünn |
| 2 | 55 | 25 % | dünn |
| 3 | 45 | 21 % | mittel |
| 4 | 18 | 8 % | nahe Ziel |
| 5 | 4 | 2 % | **Ziel erreicht** |
| 7 | 1 | < 1 % | über Ziel |
| **Gesamt** | **216** | 100 % | (24h × 3 Bänder × 3 Modi) |

**Ziel-Erreicht: 5/216 Slots = 2,3 %.**

---

## 0 Tage erfasst — 56 Slots (Priorität 1)

Alle 56 leeren Slots sind **30m** — 30m wird selten genutzt. Strategie:
mehrere Tage hintereinander auf 30m sammeln, alle 3 Modi.

```
02:00 Berlin (=00 UTC)  30m   Normal          0 Tage
02:00 Berlin (=00 UTC)  30m   Diversity Std   0 Tage
02:00 Berlin (=00 UTC)  30m   Diversity DX    0 Tage
03:00 Berlin (=01 UTC)  30m   Normal          0 Tage
03:00 Berlin (=01 UTC)  30m   Diversity Std   0 Tage
03:00 Berlin (=01 UTC)  30m   Diversity DX    0 Tage
04:00 Berlin (=02 UTC)  30m   Normal          0 Tage
04:00 Berlin (=02 UTC)  30m   Diversity Std   0 Tage
04:00 Berlin (=02 UTC)  30m   Diversity DX    0 Tage
05:00 Berlin (=03 UTC)  30m   Normal          0 Tage
05:00 Berlin (=03 UTC)  30m   Diversity Std   0 Tage
05:00 Berlin (=03 UTC)  30m   Diversity DX    0 Tage
06:00 Berlin (=04 UTC)  30m   Normal          0 Tage
06:00 Berlin (=04 UTC)  30m   Diversity Std   0 Tage
06:00 Berlin (=04 UTC)  30m   Diversity DX    0 Tage
07:00 Berlin (=05 UTC)  30m   Diversity Std   0 Tage
07:00 Berlin (=05 UTC)  30m   Diversity DX    0 Tage
09:00 Berlin (=07 UTC)  30m   Diversity Std   0 Tage
09:00 Berlin (=07 UTC)  30m   Diversity DX    0 Tage
10:00 Berlin (=08 UTC)  30m   Normal          0 Tage
10:00 Berlin (=08 UTC)  30m   Diversity DX    0 Tage
11:00 Berlin (=09 UTC)  30m   Normal          0 Tage
11:00 Berlin (=09 UTC)  30m   Diversity DX    0 Tage
12:00 Berlin (=10 UTC)  30m   Normal          0 Tage
12:00 Berlin (=10 UTC)  30m   Diversity DX    0 Tage
13:00 Berlin (=11 UTC)  30m   Normal          0 Tage
13:00 Berlin (=11 UTC)  30m   Diversity DX    0 Tage
14:00 Berlin (=12 UTC)  30m   Diversity DX    0 Tage
15:00 Berlin (=13 UTC)  30m   Diversity Std   0 Tage
15:00 Berlin (=13 UTC)  30m   Diversity DX    0 Tage
17:00 Berlin (=15 UTC)  30m   Normal          0 Tage
17:00 Berlin (=15 UTC)  30m   Diversity Std   0 Tage
18:00 Berlin (=16 UTC)  30m   Normal          0 Tage
18:00 Berlin (=16 UTC)  30m   Diversity Std   0 Tage
18:00 Berlin (=16 UTC)  30m   Diversity DX    0 Tage
19:00 Berlin (=17 UTC)  30m   Normal          0 Tage
19:00 Berlin (=17 UTC)  30m   Diversity Std   0 Tage
19:00 Berlin (=17 UTC)  30m   Diversity DX    0 Tage
20:00 Berlin (=18 UTC)  30m   Normal          0 Tage
20:00 Berlin (=18 UTC)  30m   Diversity Std   0 Tage
20:00 Berlin (=18 UTC)  30m   Diversity DX    0 Tage
21:00 Berlin (=19 UTC)  30m   Normal          0 Tage
21:00 Berlin (=19 UTC)  30m   Diversity Std   0 Tage
21:00 Berlin (=19 UTC)  30m   Diversity DX    0 Tage
22:00 Berlin (=20 UTC)  30m   Normal          0 Tage
22:00 Berlin (=20 UTC)  30m   Diversity Std   0 Tage
22:00 Berlin (=20 UTC)  30m   Diversity DX    0 Tage
23:00 Berlin (=21 UTC)  30m   Normal          0 Tage
23:00 Berlin (=21 UTC)  30m   Diversity Std   0 Tage
23:00 Berlin (=21 UTC)  30m   Diversity DX    0 Tage
00:00 Berlin (=22 UTC)  30m   Normal          0 Tage
00:00 Berlin (=22 UTC)  30m   Diversity Std   0 Tage
00:00 Berlin (=22 UTC)  30m   Diversity DX    0 Tage
01:00 Berlin (=23 UTC)  30m   Normal          0 Tage
01:00 Berlin (=23 UTC)  30m   Diversity Std   0 Tage
01:00 Berlin (=23 UTC)  30m   Diversity DX    0 Tage
```

---

## 1 Tag erfasst — 37 Slots

```
02:00 Berlin (=00 UTC)  20m   Normal          1 Tag
02:00 Berlin (=00 UTC)  20m   Diversity Std   1 Tag
03:00 Berlin (=01 UTC)  40m   Normal          1 Tag
03:00 Berlin (=01 UTC)  20m   Normal          1 Tag
03:00 Berlin (=01 UTC)  20m   Diversity Std   1 Tag
04:00 Berlin (=02 UTC)  40m   Normal          1 Tag
04:00 Berlin (=02 UTC)  20m   Normal          1 Tag
04:00 Berlin (=02 UTC)  20m   Diversity Std   1 Tag
05:00 Berlin (=03 UTC)  40m   Normal          1 Tag
05:00 Berlin (=03 UTC)  20m   Normal          1 Tag
06:00 Berlin (=04 UTC)  20m   Normal          1 Tag
07:00 Berlin (=05 UTC)  30m   Normal          1 Tag
07:00 Berlin (=05 UTC)  20m   Normal          1 Tag
08:00 Berlin (=06 UTC)  30m   Diversity Std   1 Tag
08:00 Berlin (=06 UTC)  30m   Diversity DX    1 Tag
08:00 Berlin (=06 UTC)  20m   Normal          1 Tag
08:00 Berlin (=06 UTC)  20m   Diversity DX    1 Tag
09:00 Berlin (=07 UTC)  30m   Normal          1 Tag
10:00 Berlin (=08 UTC)  30m   Diversity Std   1 Tag
11:00 Berlin (=09 UTC)  30m   Diversity Std   1 Tag
12:00 Berlin (=10 UTC)  30m   Diversity Std   1 Tag
12:00 Berlin (=10 UTC)  20m   Diversity DX    1 Tag
13:00 Berlin (=11 UTC)  40m   Normal          1 Tag
13:00 Berlin (=11 UTC)  30m   Diversity Std   1 Tag
14:00 Berlin (=12 UTC)  30m   Normal          1 Tag
14:00 Berlin (=12 UTC)  30m   Diversity Std   1 Tag
15:00 Berlin (=13 UTC)  30m   Normal          1 Tag
15:00 Berlin (=13 UTC)  20m   Diversity Std   1 Tag
16:00 Berlin (=14 UTC)  30m   Normal          1 Tag
16:00 Berlin (=14 UTC)  30m   Diversity Std   1 Tag
16:00 Berlin (=14 UTC)  30m   Diversity DX    1 Tag
17:00 Berlin (=15 UTC)  30m   Diversity DX    1 Tag
20:00 Berlin (=18 UTC)  20m   Diversity Std   1 Tag
21:00 Berlin (=19 UTC)  40m   Normal          1 Tag
22:00 Berlin (=20 UTC)  40m   Normal          1 Tag
23:00 Berlin (=21 UTC)  40m   Normal          1 Tag
01:00 Berlin (=23 UTC)  40m   Diversity DX    1 Tag
```

---

## 2 Tage erfasst — 55 Slots

```
02:00 Berlin (=00 UTC)  40m   Normal          2 Tage
02:00 Berlin (=00 UTC)  40m   Diversity DX    2 Tage
02:00 Berlin (=00 UTC)  20m   Diversity DX    2 Tage
03:00 Berlin (=01 UTC)  40m   Diversity DX    2 Tage
03:00 Berlin (=01 UTC)  20m   Diversity DX    2 Tage
04:00 Berlin (=02 UTC)  40m   Diversity DX    2 Tage
04:00 Berlin (=02 UTC)  20m   Diversity DX    2 Tage
05:00 Berlin (=03 UTC)  40m   Diversity DX    2 Tage
05:00 Berlin (=03 UTC)  20m   Diversity Std   2 Tage
05:00 Berlin (=03 UTC)  20m   Diversity DX    2 Tage
06:00 Berlin (=04 UTC)  40m   Diversity DX    2 Tage
06:00 Berlin (=04 UTC)  20m   Diversity Std   2 Tage
07:00 Berlin (=05 UTC)  20m   Diversity Std   2 Tage
08:00 Berlin (=06 UTC)  40m   Diversity Std   2 Tage
08:00 Berlin (=06 UTC)  30m   Normal          2 Tage
08:00 Berlin (=06 UTC)  20m   Diversity Std   2 Tage
09:00 Berlin (=07 UTC)  20m   Diversity Std   2 Tage
10:00 Berlin (=08 UTC)  20m   Diversity Std   2 Tage
12:00 Berlin (=10 UTC)  40m   Normal          2 Tage
12:00 Berlin (=10 UTC)  40m   Diversity Std   2 Tage
13:00 Berlin (=11 UTC)  40m   Diversity Std   2 Tage
13:00 Berlin (=11 UTC)  20m   Diversity DX    2 Tage
14:00 Berlin (=12 UTC)  40m   Normal          2 Tage
14:00 Berlin (=12 UTC)  20m   Normal          2 Tage
15:00 Berlin (=13 UTC)  40m   Normal          2 Tage
15:00 Berlin (=13 UTC)  40m   Diversity Std   2 Tage
15:00 Berlin (=13 UTC)  40m   Diversity DX    2 Tage
15:00 Berlin (=13 UTC)  20m   Normal          2 Tage
15:00 Berlin (=13 UTC)  20m   Diversity DX    2 Tage
16:00 Berlin (=14 UTC)  40m   Diversity Std   2 Tage
16:00 Berlin (=14 UTC)  20m   Diversity Std   2 Tage
17:00 Berlin (=15 UTC)  40m   Normal          2 Tage
17:00 Berlin (=15 UTC)  40m   Diversity Std   2 Tage
17:00 Berlin (=15 UTC)  40m   Diversity DX    2 Tage
17:00 Berlin (=15 UTC)  20m   Diversity Std   2 Tage
19:00 Berlin (=17 UTC)  40m   Diversity DX    2 Tage
21:00 Berlin (=19 UTC)  40m   Diversity Std   2 Tage
21:00 Berlin (=19 UTC)  20m   Diversity Std   2 Tage
21:00 Berlin (=19 UTC)  20m   Diversity DX    2 Tage
22:00 Berlin (=20 UTC)  40m   Diversity Std   2 Tage
22:00 Berlin (=20 UTC)  20m   Normal          2 Tage
22:00 Berlin (=20 UTC)  20m   Diversity Std   2 Tage
22:00 Berlin (=20 UTC)  20m   Diversity DX    2 Tage
23:00 Berlin (=21 UTC)  40m   Diversity Std   2 Tage
23:00 Berlin (=21 UTC)  20m   Normal          2 Tage
23:00 Berlin (=21 UTC)  20m   Diversity Std   2 Tage
23:00 Berlin (=21 UTC)  20m   Diversity DX    2 Tage
00:00 Berlin (=22 UTC)  40m   Normal          2 Tage
00:00 Berlin (=22 UTC)  20m   Normal          2 Tage
00:00 Berlin (=22 UTC)  20m   Diversity Std   2 Tage
00:00 Berlin (=22 UTC)  20m   Diversity DX    2 Tage
01:00 Berlin (=23 UTC)  40m   Normal          2 Tage
01:00 Berlin (=23 UTC)  20m   Normal          2 Tage
01:00 Berlin (=23 UTC)  20m   Diversity Std   2 Tage
01:00 Berlin (=23 UTC)  20m   Diversity DX    2 Tage
```

---

## 3 Tage erfasst — 45 Slots

```
04:00 Berlin (=02 UTC)  40m   Diversity Std   3 Tage
05:00 Berlin (=03 UTC)  40m   Diversity Std   3 Tage
06:00 Berlin (=04 UTC)  40m   Normal          3 Tage
06:00 Berlin (=04 UTC)  20m   Diversity DX    3 Tage
07:00 Berlin (=05 UTC)  40m   Diversity Std   3 Tage
07:00 Berlin (=05 UTC)  40m   Diversity DX    3 Tage
07:00 Berlin (=05 UTC)  20m   Diversity DX    3 Tage
08:00 Berlin (=06 UTC)  40m   Normal          3 Tage
08:00 Berlin (=06 UTC)  40m   Diversity DX    3 Tage
09:00 Berlin (=07 UTC)  40m   Normal          3 Tage
10:00 Berlin (=08 UTC)  40m   Normal          3 Tage
10:00 Berlin (=08 UTC)  20m   Diversity DX    3 Tage
12:00 Berlin (=10 UTC)  40m   Diversity DX    3 Tage
12:00 Berlin (=10 UTC)  20m   Normal          3 Tage
12:00 Berlin (=10 UTC)  20m   Diversity Std   3 Tage
13:00 Berlin (=11 UTC)  40m   Diversity DX    3 Tage
13:00 Berlin (=11 UTC)  20m   Normal          3 Tage
13:00 Berlin (=11 UTC)  20m   Diversity Std   3 Tage
14:00 Berlin (=12 UTC)  40m   Diversity Std   3 Tage
14:00 Berlin (=12 UTC)  40m   Diversity DX    3 Tage
14:00 Berlin (=12 UTC)  20m   Diversity Std   3 Tage
16:00 Berlin (=14 UTC)  40m   Normal          3 Tage
16:00 Berlin (=14 UTC)  40m   Diversity DX    3 Tage
16:00 Berlin (=14 UTC)  20m   Normal          3 Tage
16:00 Berlin (=14 UTC)  20m   Diversity DX    3 Tage
18:00 Berlin (=16 UTC)  40m   Normal          3 Tage
18:00 Berlin (=16 UTC)  40m   Diversity Std   3 Tage
18:00 Berlin (=16 UTC)  40m   Diversity DX    3 Tage
18:00 Berlin (=16 UTC)  20m   Normal          3 Tage
18:00 Berlin (=16 UTC)  20m   Diversity DX    3 Tage
19:00 Berlin (=17 UTC)  40m   Normal          3 Tage
19:00 Berlin (=17 UTC)  40m   Diversity Std   3 Tage
19:00 Berlin (=17 UTC)  20m   Diversity DX    3 Tage
20:00 Berlin (=18 UTC)  40m   Normal          3 Tage
20:00 Berlin (=18 UTC)  40m   Diversity Std   3 Tage
20:00 Berlin (=18 UTC)  40m   Diversity DX    3 Tage
20:00 Berlin (=18 UTC)  20m   Normal          3 Tage
20:00 Berlin (=18 UTC)  20m   Diversity DX    3 Tage
21:00 Berlin (=19 UTC)  40m   Diversity DX    3 Tage
21:00 Berlin (=19 UTC)  20m   Normal          3 Tage
22:00 Berlin (=20 UTC)  40m   Diversity DX    3 Tage
23:00 Berlin (=21 UTC)  40m   Diversity DX    3 Tage
00:00 Berlin (=22 UTC)  40m   Diversity Std   3 Tage
00:00 Berlin (=22 UTC)  40m   Diversity DX    3 Tage
01:00 Berlin (=23 UTC)  40m   Diversity Std   3 Tage
```

---

## 4 Tage erfasst — 18 Slots (nahe Ziel)

```
02:00 Berlin (=00 UTC)  40m   Diversity Std   4 Tage
03:00 Berlin (=01 UTC)  40m   Diversity Std   4 Tage
06:00 Berlin (=04 UTC)  40m   Diversity Std   4 Tage
07:00 Berlin (=05 UTC)  40m   Normal          4 Tage
09:00 Berlin (=07 UTC)  40m   Diversity Std   4 Tage
09:00 Berlin (=07 UTC)  40m   Diversity DX    4 Tage
09:00 Berlin (=07 UTC)  20m   Diversity DX    4 Tage
10:00 Berlin (=08 UTC)  40m   Diversity DX    4 Tage
11:00 Berlin (=09 UTC)  40m   Normal          4 Tage
11:00 Berlin (=09 UTC)  40m   Diversity Std   4 Tage
11:00 Berlin (=09 UTC)  40m   Diversity DX    4 Tage
11:00 Berlin (=09 UTC)  20m   Diversity Std   4 Tage
11:00 Berlin (=09 UTC)  20m   Diversity DX    4 Tage
14:00 Berlin (=12 UTC)  20m   Diversity DX    4 Tage
17:00 Berlin (=15 UTC)  20m   Normal          4 Tage
17:00 Berlin (=15 UTC)  20m   Diversity DX    4 Tage
18:00 Berlin (=16 UTC)  20m   Diversity Std   4 Tage
19:00 Berlin (=17 UTC)  20m   Normal          4 Tage
```

---

## 5 Tage erfasst — 4 Slots (Ziel erreicht ✓)

```
09:00 Berlin (=07 UTC)  20m   Normal          5 Tage
10:00 Berlin (=08 UTC)  40m   Diversity Std   5 Tage
10:00 Berlin (=08 UTC)  20m   Normal          5 Tage
19:00 Berlin (=17 UTC)  20m   Diversity Std   5 Tage
```

---

## 7 Tage erfasst — 1 Slot

```
11:00 Berlin (=09 UTC)  20m   Normal          7 Tage
```
