# SC4NEON.dll — scheletro della DLL per NEON

Versione 0.3.4 · 25 ottobre 2026 · da compilare e provare in gioco

La DLL sposta in C++ i calcoli di `run_grid_balance_variables()` di NEON_LUA. I reward restano in Lua.
Sui 300 casi di prova casuali la versione C++ dà gli stessi ~237 valori della versione Lua originale
(tutti i campi di `grid_logic_var` e `power_company_buildings` e i sei valori di ritorno T, D, X, I, B, P).
L'unica differenza voluta riguarda la geotermia (vedi "Differenze rispetto al Lua").

## Cosa fa

| Parte | File | Cosa fa |
| --- | --- | --- |
| Controllo exemplar | `src/NeonDllDirector.cpp`, `src/NeonRules.cpp` | Con SC4ResourceLoadingHooks.dll installata, a ogni caricamento di exemplar di una centrale NEON (dopo le patch): se mancano li scrive (MWh = potenza prodotta 0x27812852, kVA = 2,5 × MWh); se ci sono e non tornano, li lascia e li segnala; segnala la classe di carico mancante o doppia. Tutto finisce in `SC4NEON.log`. |
| Modello della rete | `src/NeonGridModel.cpp` | Tiene il conto degli edifici NEON quando entrano o escono dalla città (messaggi 0x99EF1142 / 0x99EF1143, verificati nell'exe) e ricalcola i valori solo quando cambia qualcosa. Sostituisce le 1.183 chiamate a `get_source_building_count` di ogni valutazione. |
| Ponte Lua | `src/NeonLua.cpp`, `lua/neon_dll_bridge.lua` | Registra la tabella `neon` (`update`, `export`, `grid`, `count`, `version`). Il ponte in NEON_LUA passa alla DLL gli stessi valori di gioco che usava il Lua e riceve indietro tutti i campi. |
| Classe di carico | `src/NeonRules.cpp` | Regola concordata: la classe (Base Load 0x18E64EA5, Intermediate 0x0BADB9AC, Peak 0x7283DCD7) deve essere nell'exemplar. I totali `SUP_GEN_I/B/P_POWER` usano la classe dell'exemplar; se manca, la DLL usa il raggruppamento del Lua e lo segnala nel log. |

## Centrali non supportate

Una centrale senza gruppi NEON né vecchi gruppi 0xBB35xxxx viene contata a parte, per tipo Maxis (0x27812853): `UNS_COAL_COUNT`, `UNS_NAT_GAS_COUNT`, `UNS_OIL_COUNT`, `UNS_WIND_COUNT`, `UNS_SOLAR_COUNT`, `UNS_FISSION_COUNT`, `UNS_WASTE_COUNT`, `UNS_FUSION_COUNT`, `UNS_OTHER_COUNT`, più `LARGE_OTHER_COUNT`, `SMALL_OTHER_COUNT` e `D_OTHER_POWER` (MWh). Sono i valori che i testi dell'ufficio della compagnia elettrica richiamano; senza la DLL il ponte Lua li mette a 0.

## NEON_LUA

Ci sono due versioni, generate dallo stesso originale:

| File | Senza SC4NEON.dll | Usata nella mod |
| --- | --- | --- |
| `lua/NEON_LUA_DLL_ONLY.txt` | la rete resta a 0, i reward NEON restano bloccati e il consigliere avvisa che manca la DLL | **sì** (NEON_Core_Files.dat della V 0.1.2) |
| `lua/NEON_LUA.txt` | usa la versione Lua originale (`run_grid_balance_variables_lua`) | no, resta come riferimento |

La versione solo DLL si rigenera con `python tools/make_dll_only.py lua/NEON_LUA.txt <dump LTEXT .json> lua/NEON_LUA_DLL_ONLY.txt`. Rispetto alla versione con riserva:

- tolta la versione Lua di `run_grid_balance_variables` (387 righe, con tutte le chiamate a `get_source_building_count`);
- `kva_rating` ridotta da 444 a 34 voci e `mwh_rating` da 480 a 84: restano solo quelle lette dai reward, dagli LTEXT e dall'aggiornamento dei termovalorizzatori;
- `kva_rating.ID_BB3501A4` (centrale a gas Maxis) ora legge la proprietà kVA 0xE652E51F invece di quella MWh;
- nuovo messaggio del consigliere (testi 6A231EA4/BB354201 e BB354301 in NEON_Locale_Files_en.dat) se la DLL manca;
- il file passa da 3.509 a 2.324 righe.

Con la DLL, `run_grid_balance_variables()` chiama `neon.update(...)` e, se qualcosa è cambiato, `neon.export(grid_logic_var, power_company_buildings)`, poi aggiorna la produzione reale dei termovalorizzatori (`mwh_rating.ID_BB35xxDx`), che la query W2E mostra. Le condizioni dei reward e gli LTEXT non cambiano.

Alcune voci rimaste in `kva_rating` / `mwh_rating` leggono ancora l'exemplar con `dbpf.get_exemplar_property_value`: per ora serve ancora sc4-lua-extensions.

## Compilare

Serve Visual Studio (2022 o successivo) con il carico di lavoro "Sviluppo di applicazioni desktop con C++".

1. Apri `SC4NEON.sln`.
2. Menu **Compila → Compila soluzione**.

La soluzione ha solo la configurazione **Release / x86** (SimCity 4 è un gioco a 32 bit), quindi non c'è niente da scegliere.

Il risultato è `bin\Release\SC4NEON.dll`. Va nella cartella Plugins insieme a `SC4ResourceLoadingHooks.dll` (facoltativa ma consigliata), a sc4-lua-extensions e alla mod NEON V 0.1.2. Con la V 0.1.2 la DLL è obbligatoria.

Il progetto usa il set di strumenti C++ della versione di Visual Studio installata (2019 16.11 o successiva, 2022, 2026), quindi non serve "Ridestina soluzione". Se manca la Windows SDK, installala dal programma di installazione di Visual Studio.

In alternativa c'è `CMakeLists.txt`: `cmake -S . -B build -A Win32` e poi `cmake --build build --config Release` (il risultato va in `build/Release`).

Tutto il necessario è nella cartella: gli header e i 5 file .cpp di gzcom-dll che servono sono in `vendor/gzcom-dll` (LGPL 2.1, commit in `vendor/gzcom-dll/SOURCE.txt`), gli header pubblici di sc4-resource-loading-hooks (MIT) in `vendor/sc4-resource-loading-hooks/include`. Se la DLL viene distribuita, valgono gli obblighi della LGPL di gzcom-dll (come per le DLL di null45).

## Prove fatte (fuori dal gioco)

| Prova | Comando | Risultato |
| --- | --- | --- |
| C++ contro Lua originale, 300 città casuali senza geotermia | `python tests/compare_with_lua.py NEON_LUA.txt <model_driver> 300 --exclude-geo` | 0 differenze |
| Ponte Lua, 40 città, senza DLL e con DLL | `python tests/bridge_test.py <originale> lua/NEON_LUA.txt <model_driver>` | 0 differenze in entrambi i casi |
| Versione solo DLL, 100 città con DLL; senza DLL; 71 condizioni dei reward e tutti i trigger, con e senza DLL | `python tests/dll_only_test.py <originale> lua/NEON_LUA.txt lua/NEON_LUA_DLL_ONLY.txt <model_driver>` | 0 differenze; senza DLL restituisce 0 e nessun errore |
| Regole degli exemplar | `tests/rules_test.cpp` | passa |
| Controllo sintattico dei sorgenti DLL sugli header gzcom-dll (tranne `NeonLog.cpp`, che richiede Windows.h) | clang `-fsyntax-only` | nessun errore |

I test si lanciano dalla cartella del progetto e usano `lupa` (`pip install lupa`). `model_driver` si compila con qualunque compilatore C++20: `g++ -std=c++20 tests/model_driver.cpp src/NeonGridModel.cpp -o model_driver`.

**Non provato:** il collegamento (link) con MSVC e il funzionamento dentro SimCity 4. È il primo passo da fare su Windows.

## Strumento di controllo dei .dat

`tools/neon_audit.py` applica le stesse regole della DLL ai file .dat, prima di avviare il gioco. Applica anche le patch, se trova l'exemplar a cui sono destinate.

```
python tools/neon_audit.py "C:\...\SimCity 4\Plugins"
```

Sul file CAM allegato segnala la classe di carico mancante su tutte le 8 centrali; MWh e kVA sono corretti.

## Differenze rispetto al Lua

- **Geotermia**: nel Lua `LARGE_GEO_RATING`, `L_GEOTHERMAL_POWER` e `S_GEOTHERMAL_POWER` valevano sempre 0, quindi l'ufficio mostrava 0 MWh e 0 kVA per le centrali geotermiche. La DLL li calcola dai gruppi geotermici.
- **Tidal e Microwave**: il Lua non ha gruppi vecchi per loro. La DLL conta gli edifici con il gruppo NEON Tidal (0xF0D606AC) o Microwave (0x0CED62DC) e ne riempie conteggi, kVA e MWh.
- **Rating**: il Lua usava i valori delle tabelle; la DLL usa quelli dell'exemplar (dopo le patch) e ricorre alle tabelle solo se l'exemplar non li ha. Con la versione solo DLL, `neon.export` scrive anche in `kva_rating` / `mwh_rating` i valori medi dei lotti presenti in città, così le schermate mostrano i valori veri del lotto.

## Strumenti per i file della mod

`tools/mod/` contiene gli script usati per correggere la Colossus Addon Mod (lettura e scrittura DBPF che lascia identici i file non modificati, controllo dei riferimenti UI → testi, valutazione di ogni espressione `#...#` dei testi contro il Lua con la DLL).

## Reward e bilanciamento (0.3.0)

Le condizioni delle centrali Maxis (carbone, gas, eolico, petrolio, fissione, fusione, solare, termovalorizzatore) sono quelle originali di NEON (ripristinate nella 0.3.4).

Priorità alle centrali Maxis (CAM_Power_Garbage_Buildings.dat), perché non tutti installano i lotti di terzi.

**Valori dai lotti installati.** All'apertura della città la DLL scrive in `kva_rating` / `mwh_rating` la media di kVA e MWh dei lotti installati di ogni gruppo (dagli exemplar, dopo le patch), poi quelli dei lotti in città. Le soglie dei reward usano quindi i valori veri anche per le centrali non ancora costruite. `neon.installed(gruppo)` dice se un lotto di quel gruppo è nei Plugins.

**Dipendenze obbligatorie.** Trasformatori, sottostazioni di distribuzione e stazioni di trasmissione sono dipendenze obbligatorie di NEON: la catena centrali → trasmissione → distribuzione → trasformatori è sempre richiesta, per i reward e per i limiti della rete. All'apertura della città la DLL conta i lotti installati di ogni tipo; se un tipo manca lo scrive nel log come errore e il consigliere avvisa (testi 6A231EA4/BB354203 e BB354303; `grid_logic_var.NEON_MISSING_DEPENDENCIES` = numero di tipi mancanti).

| Tipo | Lotti con patch NEON |
| --- | --- |
| Trasformatori | KK Transformer Lots (inclusi nella mod: 250 kVA, 500 kVA, 1,5 MVA, 3 MVA, 6 MVA) |
| Distribuzione | SM2 HV Transformer, DK1 Substation, PEG Power SubStation2, SM2 Main Transformer, SM2 Main Transformer with building, PEG Power Sub-Station, SM2 Power Transformer 1 e 2 |
| Trasmissione | **2x2 Maxis Power Substation (88630077), inclusa nella mod**: 10 MVA, gruppo NEON HV Transformers, condizionale; usa modelli e props della Transformer Substation di Takingyouthere, che va installata (il suo lotto 64A800CD va tolto); Homefryes Substation 1–4, SM2 Power Transformer 3, SM2 Power Substation |

| Reward | Prima | Ora |
| --- | --- | --- |
| PEG GeoThermal 10 MW | leggeva il gruppo inesistente BB350063 (0 kVA) | BB350071 (15.000 kVA) |
| SM2 Geothermal | spazio Base libero 4.600 MWh | 25.000 MWh (la sua produzione) |
| SM2 Sim Gideon NG | `game.g_power_consumed` | `MWH_DEMAND_TOTAL`, come le altre |
| Tesla Powerpack XS/SM/MD/LG | 15 / 30 / 76 / 300 MWh di generazione I+B | 1.500 / 3.000 / 7.000 / 28.000 (≈ MW × 750, la scala del gioco) |
| Sottostazioni di distribuzione 1/2/7/10/15/25 MVA | domanda 2.000/5.000/2.500/10.000/15.000/25.000 MWh | kVA / 2,5: 400/800/2.800/4.000/6.000/10.000 |
| Stazioni di trasmissione 20/35/60/60S/90/120 MVA | 3.000/10.000/30.000/30.000/50.000/70.000 MWh | metà di kVA / 2,5: 4.000/7.000/12.000/12.000/18.000/24.000 |

Tabelle `kva_rating` / `mwh_rating` allineate alla regola 2,5 × MWh per i lotti verificati: SM2 Geothermal 62.500 / 25.000, PEG GeoThermal 15.000, PEG GeoThermal Small 5.500, SM2 Sim Gideon 73.750 / 29.500, SG Hardun 15.000 / 6.000, Medium Clean Coal 52.500, SM2 GE Solar 6.250 / 2.500, Chicago Union Station 3.125, pannelli SM2 100 MWh, generatore SM2 L 1.500 MWh.

## Limiti reali della rete (0.2.0)

Con `Enabled=1` in `SC4NEON.ini` (creato accanto alla DLL al primo avvio) l'energia che NEON dice di non poter consegnare non arriva davvero agli edifici.

**Come funziona.** `cSC4PowerSimulator::UpdatePowerGrid` (0x006EE110) calcola l'energia distribuibile come produzione × 1,1 con l'istruzione `fmul dword ptr [0x00AB2888]` (il float −1,1, letto solo lì), poi alimenta i blocchi 8×8 in ordine casuale finché l'energia basta. La DLL riscrive quel valore a ogni `neon.update`, quindi il gioco distribuisce solo `domanda − blackout`: i blocchi rimasti senza energia sono le interruzioni. Nessuna istruzione del gioco viene modificata; se l'exe non è la 1.1.641 la DLL non tocca niente e lo scrive nel log. Alla chiusura della città il valore torna 1,1.

**Cosa limita** (MWh al mese):

| Limite | Calcolo | Impostazione |
| --- | --- | --- |
| Bilancio di carico | `USED_I + USED_B + USED_P`: quota Base, Intermediate e Peak servibile (le importazioni contano nel Peak) | `LoadBalance` |
| Infrastruttura | centrali grandi + importazioni → stazioni di trasmissione → sottostazioni di distribuzione → trasformatori; le piccole centrali entrano dalla distribuzione; i generatori consegnano direttamente. Capacità in MWh = kVA / 2,5 | `Infrastructure` |

`deficit = domanda − min(limiti attivi)`, `blackout = deficit × forza`, dove la forza sale da 0 a `StartPopulation` a 1 a `FullPopulation` abitanti residenziali (predefiniti 3.000 e 15.000), così una città nuova può crescere e sbloccare trasformatori e centrali di picco.

I valori sono in `grid_logic_var`: `NEON_DELIVERABLE_POWER`, `NEON_LOADBALANCE_POWER`, `NEON_INFRASTRUCTURE_POWER`, `NEON_BLACKOUT_POWER`, `NEON_ENFORCE_STRENGTH`, `NEON_ENFORCE_FACTOR`. Il consigliere avvisa al primo taglio (testi 6A231EA4/BB354202 e BB354302). Il log scrive una riga quando il taglio cambia.

Prova del calcolo: `tests/enforcement_test.cpp`.

## Correzioni

- **NEON_LUA (25 ott 2026)** – le 69 reward di NEON sono consegnate dal consigliere delle Utilità invece che dall'Urbanista: nuova funzione `create_reward_utilities` (come `create_reward_cityplanning` di Maxis, con il tipo di consiglio UTILITIES), definita solo se un'altra mod non la definisce già.
- **0.3.4** – condizioni originali delle centrali Maxis. CAM Electric Generator (55FDAF8F/561E640A, CAM_Maxis_Building_Extended.dat): generatore a gas NEON, Peak, 800 MWh / 2.000 kVA, gruppo BB350101 (generatori a gas #2) e finestra BB353101; sempre disponibile.
- **0.3.3** – un edificio senza gruppi NEON conta come "centrale non supportata" solo se ha anche il tipo di centrale Maxis (0x27812853): parchi o landmark con 1 MWh di "power produced" non finiscono più nell'ufficio. Il log scrive "large/small" solo per le centrali.
- **0.3.2** – ogni 10 secondi di gioco (al primo `neon.update`) la DLL ricontrolla gli edifici della città e corregge il conteggio se ha perso un messaggio "occupant inserted/removed" (lo scrive nel log come "Resync"). La capacità dell'infrastruttura nei limiti della rete non viene più ingrandita quando il gioco produce più energia delle centrali contate da NEON.
- **0.1.3** – i valori di un edificio (gruppi, MWh, kVA) vengono dall'exemplar del suo tipo, letto al caricamento, e non dalle proprietà dell'edificio in città (servono solo se manca SC4ResourceLoadingHooks.dll). Il log scrive una riga per ogni tipo di edificio contato, con MWh, kVA, classe e gruppi. Nuovo gruppo NEON 0xBB350079 (Large Fission #2) per la VVER-1000 di BurroDiablo, contato con le altre centrali a fissione grandi.
- **0.1.2** – il log riporta ogni exemplar una sola volta, con i gruppi dell'edificio quando c'è un problema, e all'apertura della città scrive quanti edifici ha visto e quanti ne conta NEON.
- **0.1.2** – crash all'apertura della città (ACCESS_VIOLATION in `NeonDllDirector::AddOccupant`): i gruppi dell'edificio erano letti con `cISC4Occupant::GetOccupantGroups`, che riempie un `std::set` con la STL del gioco (Visual C++ 2003), incompatibile con quella di Visual Studio attuale. Ora la DLL legge la proprietà OccupantGroups (0xAA1DD396) dell'edificio, come fa già per gli exemplar.

## Domande aperte

1. **Centrali piccole e grandi.** Per una centrale con solo il gruppo NEON (senza vecchio gruppo 0xBB35xxxx) la DLL decide "grande" se MWh ≥ 8000 (`NeonRules::kLargePlantMinMwh`). È un valore provvisorio e non riproduce il Lua: la centrale a carbone Maxis (7500 MWh) era grande, la solare Maxis (8000 MWh) era piccola. Serve una regola: una proprietà o un gruppo "Small/Large" nell'exemplar, oppure una soglia diversa.
2. **Trasformatori.** Mappatura provvisoria: HV → TRANSMISSION, MV → DISTRIBUTE_A, LV → TRANSFORMER, Auxiliary → MISC_ELEC_F, Power Storage → BATTERY_LOT. Va confermata.
3. **Edifici solo con gruppi vecchi**: sedi della compagnia elettrica (0xBB350200–204), pannelli fotovoltaici, step-up e inverter esistono solo come gruppi 0xBB35xxxx. Funzionano, ma non hanno ancora un equivalente nei nuovi gruppi NEON.
