# Solar za firme: brza procena isplativosti

Web alat koji za par sekundi daje okvirnu procenu isplativosti solarne elektrane na krovu firme u Srbiji.

**👉 Probajte aplikaciju: [solar-procena-ugordic.streamlit.app](https://solar-procena-ugordic.streamlit.app/)**

![Primer rezultata: firma u Kragujevcu, 100 MWh godišnje, rad pon–pet 9–17 i subotom](snimak.png)

**Ulaz:** lokacija, potrošnja struje (godišnja ili po mesecima), radno vreme firme, cena struje, prodaja viška, površina krova.
**Izlaz:** preporučena snaga, investicija, godišnja ušteda, period povrata, mesečni bilans i zarada u zavisnosti od snage.

## Kako radi
1. Preuzima tipičnu meteorološku godinu za lokaciju iz [PVGIS](https://re.jrc.ec.europa.eu/pvg_tools/en/) (Evropska komisija).
2. Računa satnu proizvodnju elektrane modelom [pvlib](https://pvlib-python.readthedocs.io/) (PVWatts, gubici sistema, temperatura, invertor).
3. Pravi satni profil potrošnje iz mesečnih podataka i radnog vremena.
4. Za svaki sat u godini poredi proizvodnju i potrošnju: sopstvena potrošnja, višak, struja iz mreže.
5. Računa novčani tok za 25 godina, NPV i period povrata, i bira snagu sa najvećim NPV-om kad se višak ne prodaje (oprezna preporuka).

## Pokretanje lokalno
```
pip install -r requirements.txt
streamlit run app.py
```

## Kontakt na stranici (Streamlit Secrets)
Kontakt se ne upisuje u kod, jer je kod javan. Na share.streamlit.io: aplikacija → ⋮ → **Settings** → **Secrets**, pa upisati:
```
KONTAKT_IME = "Ime Prezime"
KONTAKT_EMAIL = "email@primer.com"
KONTAKT_TELEFON = "+381 ..."
```

## Napomena
Rezultat je okvirna procena, a ne ponuda ni tehnički projekat. Za detaljnu analizu (stvarni podaci sa brojila, baterija, scenariji cena, izveštaj) koristi se proširena verzija modela.

---

# Solar for businesses: quick feasibility estimate

**Live app: [solar-procena-ugordic.streamlit.app](https://solar-procena-ugordic.streamlit.app/)**

A web tool that gives a rough estimate of rooftop solar profitability for businesses in Serbia: PVGIS irradiance + pvlib model, hourly self-consumption balance and a 25-year cash flow (NPV, payback). The recommended size maximizes NPV assuming surplus energy is not sold (conservative).
