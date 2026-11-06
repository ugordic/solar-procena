"""
Brza procena isplativosti solarne elektrane za firme.
Demo alat: proizvodnja iz PVGIS (Evropska komisija) + pvlib, satni bilans i ekonomija.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pvlib
import streamlit as st

# ================== PODEŠAVANJA (menjaš ti, ne posetilac) ==================
KONTAKT_IME = 'Uros Gordic'
KONTAKT_EMAIL = 'ugordic.@gmail.com'
KONTAKT_TELEFON = '+381 69844 9661'                    # npr. '+381 69844 9661', ili prazno

NAGIB = 30                              # nagib panela [°]
AZIMUT = 180                            # jug
DC_AC = 1.2
CENA_SOLARA = 650                       # €/kWp ključ u ruke (okvirno)
CENA_VISKA_PRODAJA = 0.05               # €/kWh, ako firma prodaje višak
ODRZAVANJE = 0.01                       # udeo investicije godišnje
DEGRADACIJA = 0.005
RAST_CENE = 0.02
DISKONTNA_STOPA = 0.07
VEK = 25
BAZNA_UDEO = 0.15                       # potrošnja van radnog vremena / u radno vreme

GRADOVI = {                             # (lat, lon, nadmorska visina) okvirno, centar grada
    'Beograd': (44.81, 20.46, 117), 'Novi Sad': (45.25, 19.84, 80), 'Niš': (43.32, 21.90, 195),
    'Kragujevac': (44.01, 20.91, 185), 'Subotica': (46.10, 19.67, 114), 'Zrenjanin': (45.38, 20.39, 80),
    'Pančevo': (44.87, 20.64, 77), 'Čačak': (43.89, 20.35, 242), 'Kraljevo': (43.72, 20.69, 205),
    'Kruševac': (43.58, 21.33, 166), 'Jagodina': (43.98, 21.26, 116), 'Novi Pazar': (43.14, 20.51, 496),
    'Valjevo': (44.27, 19.89, 185), 'Šabac': (44.75, 19.69, 80), 'Smederevo': (44.66, 20.93, 80),
    'Leskovac': (42.99, 21.95, 228), 'Vranje': (42.55, 21.90, 487), 'Užice': (43.86, 19.84, 411),
    'Sombor': (45.77, 19.11, 88), 'Zaječar': (43.90, 22.27, 144),
}
TIPOVI_RADA = {
    'Kancelarija / proizvodnja (pon–pet 7–15, sub 7–13)': {**{d: (7, 15) for d in range(5)}, 5: (7, 13)},
    'Dve smene (pon–pet 6–22)': {d: (6, 22) for d in range(5)},
    'Trgovina (pon–sub 8–20)': {d: (8, 20) for d in range(6)},
    'Ugostiteljstvo (svaki dan 12–23)': {d: (12, 23) for d in range(7)},
    'Neprekidan rad (24/7)': {d: (0, 24) for d in range(7)},
}
MESECI = ['Jan', 'Feb', 'Mar', 'Apr', 'Maj', 'Jun', 'Jul', 'Avg', 'Sep', 'Okt', 'Nov', 'Dec']


def br(x, dec=0):
    s = f'{x:,.{dec}f}'
    return s.replace(',', 'X').replace('.', ',').replace('X', '.')


# ================== PRORAČUN ==================
@st.cache_data(show_spinner=False, ttl=7 * 24 * 3600)
def proizvodnja_po_kwp(lat, lon, visina):
    """Satna proizvodnja [kW] za 1 kWp, tipična godina iz PVGIS-a, lokalno vreme."""
    tmy, _ = pvlib.iotools.get_pvgis_tmy(lat, lon, map_variables=True, coerce_year=2023, timeout=60)
    tmy = tmy.sort_index()
    lok = pvlib.location.Location(lat, lon, tz='Europe/Belgrade', altitude=visina)
    sistem = pvlib.pvsystem.PVSystem(
        surface_tilt=NAGIB, surface_azimuth=AZIMUT,
        module_parameters={'pdc0': 1000, 'gamma_pdc': -0.0035},
        inverter_parameters={'pdc0': 1000 / DC_AC / 0.96, 'eta_inv_nom': 0.96},
        temperature_model_parameters=pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_polymer'],
        losses_parameters={},
    )
    mc = pvlib.modelchain.ModelChain(sistem, lok, aoi_model='physical', spectral_model='no_loss', losses_model='pvwatts')
    mc.run_model(tmy)
    return (mc.results.ac.clip(lower=0) / 1000).tz_convert('Europe/Belgrade')


def profil_potrosnje(index, mesecno_kwh, radno_vreme):
    oblik = pd.Series(BAZNA_UDEO, index=index)
    for dan, (od, do) in radno_vreme.items():
        maska = (index.dayofweek == dan) & (index.hour >= od) & (index.hour < do)
        oblik[maska] = 1.0
    mesec = index.month
    skala = pd.Series(mesecno_kwh, index=range(1, 13)) / oblik.groupby(mesec).sum()
    return oblik * skala.reindex(mesec).values


def analiza(kwp, pv1, potr, cena_kupovine, cena_viska):
    proizv = pv1.values * kwp
    p = potr.values
    iz_mreze = np.clip(p - proizv, 0, None)
    u_mrezu = np.clip(proizv - p, 0, None)
    pokriveno = p.sum() - iz_mreze.sum()
    investicija = kwp * CENA_SOLARA
    tok = [-investicija]
    for g in range(1, VEK + 1):
        f = ((1 + RAST_CENE) * (1 - DEGRADACIJA)) ** (g - 1)
        tok.append((pokriveno * cena_kupovine + u_mrezu.sum() * cena_viska) * f - investicija * ODRZAVANJE)
    tok = np.array(tok)
    npv = sum(t / (1 + DISKONTNA_STOPA) ** g for g, t in enumerate(tok))
    kum = np.cumsum(tok)
    povrat = None
    for g in range(1, len(kum)):
        if kum[g] >= 0:
            povrat = g - 1 + (-kum[g - 1]) / tok[g]
            break
    return {
        'kwp': kwp, 'investicija': investicija, 'proizvodnja': proizv.sum(), 'potrosnja': p.sum(),
        'u_mrezu': u_mrezu.sum(), 'pokriveno': pokriveno,
        'sopstvena': (proizv.sum() - u_mrezu.sum()) / proizv.sum() * 100 if kwp else 0,
        'samodovoljnost': pokriveno / p.sum() * 100,
        'usteda': pokriveno * cena_kupovine + u_mrezu.sum() * cena_viska,
        'npv': npv, 'povrat': povrat, 'ukupno': kum[-1],
        'proizv_satno': proizv, 'u_mrezu_satno': u_mrezu,
    }


# ================== STRANICA ==================
st.set_page_config(page_title='Solar za firme: brza procena', page_icon='☀️', layout='centered')
st.title('☀️ Da li se vašoj firmi isplati solarna elektrana?')
st.write('Unesite nekoliko podataka i za par sekundi dobićete okvirnu procenu: koliku elektranu, '
         'koliko košta, koliko štedi i za koliko godina se vraća.')

with st.form('unos'):
    grad = st.selectbox('Lokacija', list(GRADOVI) + ['Druga lokacija (unos koordinata)'])
    if grad.startswith('Druga'):
        c1, c2 = st.columns(2)
        lat = c1.number_input('Geografska širina', value=44.81, format='%.4f')
        lon = c2.number_input('Geografska dužina', value=20.46, format='%.4f')
        visina = 150
    else:
        lat, lon, visina = GRADOVI[grad]

    nacin = st.radio('Potrošnja struje', ['Godišnja (jedan broj)', 'Po mesecima (sa računa)'], horizontal=True)
    if nacin.startswith('Godišnja'):
        godisnje = st.number_input('Godišnja potrošnja [kWh]', min_value=1000, value=100000, step=1000)
        mesecno = [godisnje / 12] * 12
    else:
        tab = st.data_editor(pd.DataFrame({'Mesec': MESECI, 'kWh': [8000] * 12}), hide_index=True,
                             disabled=['Mesec'])
        mesecno = tab['kWh'].astype(float).tolist()

    tip = st.selectbox('Kada firma radi?', list(TIPOVI_RADA))
    cena = st.number_input('Cena struje [€/kWh], ukupno sa računa, bez PDV-a', min_value=0.03, max_value=0.60,
                           value=0.15, step=0.01, format='%.2f')
    prodaja = st.checkbox(f'Firma bi prodavala višak struje (procena {br(CENA_VISKA_PRODAJA, 2)} €/kWh)', value=False)
    krov = st.number_input('Najveća snaga koja staje na krov [kWp], 0 ako ne znate', min_value=0, value=0, step=5)
    poslato = st.form_submit_button('Izračunaj', type='primary')

if not poslato:
    st.caption('Proizvodnja se računa iz satelitskih podataka o zračenju (PVGIS, Evropska komisija) za izabranu lokaciju.')
    st.stop()

if sum(mesecno) <= 0:
    st.error('Unesite potrošnju veću od nule.')
    st.stop()

with st.spinner('Preuzimam podatke o Suncu za lokaciju i računam...'):
    try:
        pv1 = proizvodnja_po_kwp(lat, lon, visina)
    except Exception:
        st.error('Podaci o zračenju (PVGIS) trenutno nisu dostupni. Pokušajte ponovo za par minuta.')
        st.stop()
    potr = profil_potrosnje(pv1.index, mesecno, TIPOVI_RADA[tip])
    cena_viska = CENA_VISKA_PRODAJA if prodaja else 0.0

    # Snage za proveru: do 1,5 puta snage koja bi godišnje pokrila svu potrošnju
    kwp_pun = potr.sum() / pv1.sum()
    gornja = kwp_pun * 1.5 if not krov else min(krov, kwp_pun * 1.5)
    korak = max(1, round(gornja / 40))
    snage = list(range(korak, int(gornja) + korak, korak))
    # Preporuka: najveći NPV kad se višak NE prodaje (oprezno), pa prikaz sa izabranom cenom viška
    opr = [analiza(k, pv1, potr, cena, 0.0) for k in snage]
    kwp_prep = max(opr, key=lambda r: r['npv'])['kwp']
    if krov:
        kwp_prep = min(kwp_prep, krov)
    r = analiza(kwp_prep, pv1, potr, cena, cena_viska)
    sve = [analiza(k, pv1, potr, cena, cena_viska) for k in snage]

if r['npv'] <= 0 or r['povrat'] is None:
    st.warning('Pod ovim pretpostavkama solarna elektrana se ne isplati. Za proveru sa tačnim podacima javite se za detaljnu analizu.')

st.subheader(f'Preporučena snaga: oko {br(kwp_prep)} kWp')
c1, c2, c3 = st.columns(3)
c1.metric('Investicija', f'{br(r["investicija"])} €')
c2.metric('Ušteda godišnje', f'{br(r["usteda"])} €')
c3.metric('Povrat investicije', f'{br(r["povrat"], 1)} god' if r['povrat'] else '–')
c1, c2, c3 = st.columns(3)
c1.metric('Proizvodnja', f'{br(r["proizvodnja"] / 1000)} MWh/god')
c2.metric('Solar pokriva', f'{br(r["samodovoljnost"])} % potrošnje')
c3.metric(f'Ukupno za {VEK} godina', f'{br(r["ukupno"])} €')

st.write(f'Firma bi sama iskoristila **{br(r["sopstvena"])} %** proizvedene struje'
         + (f', a višak bi prodavala po oko {br(cena_viska, 2)} €/kWh.' if prodaja
            else '. Višak se ne prodaje, pa je snaga izabrana tako da firma većinu proizvodnje iskoristi sama.'))

# Grafik 1: mesečni bilans
idx = pv1.index
df = pd.DataFrame({'potrosnja': potr.values, 'proizv': r['proizv_satno'], 'visak': r['u_mrezu_satno']}, index=idx)
m = df.groupby(idx.month).sum() / 1000
x = np.arange(12)
fig, ax = plt.subplots(figsize=(8, 3.4))
ax.bar(x - 0.2, m['potrosnja'], 0.4, color='#4A6FA5', label='Potrošnja firme')
ax.bar(x + 0.2, m['proizv'] - m['visak'], 0.4, color='#E8A33D', label='Solar, iskorišćeno u firmi')
ax.bar(x + 0.2, m['visak'], 0.4, bottom=m['proizv'] - m['visak'], color='#F3D19C', label='Solar, višak')
ax.set_xticks(x, MESECI)
ax.set_ylabel('MWh')
ax.legend(fontsize=8, ncol=3, loc='upper center', bbox_to_anchor=(0.5, 1.18), frameon=False)
ax.spines[['top', 'right']].set_visible(False)
st.pyplot(fig)

# Grafik 2: kako zarada zavisi od snage
fig2, ax2 = plt.subplots(figsize=(8, 3))
ax2.plot([s['kwp'] for s in sve], [s['npv'] / 1000 for s in sve], color='black', lw=2, label='Sa izabranim uslovima')
if prodaja:
    ax2.plot([s['kwp'] for s in opr], [s['npv'] / 1000 for s in opr], color='gray', lw=1.5, ls='--', label='Ako se višak ne proda')
ax2.axvline(kwp_prep, color='#E8A33D', lw=2, label='Preporuka')
ax2.axhline(0, color='gray', lw=0.8)
ax2.set_xlabel('Snaga elektrane [kWp]')
ax2.set_ylabel('Zarada (NPV) [hilj. €]')
ax2.legend(fontsize=8)
ax2.spines[['top', 'right']].set_visible(False)
st.pyplot(fig2)
st.caption('NPV je zarada tokom 25 godina posle povraćaja investicije, preračunata u današnji novac. '
           'Preporuka je snaga koja najviše zarađuje i kad se višak ne prodaje.')

st.divider()
st.subheader('Želite tačnu procenu?')
st.write('Ova procena koristi prosečne cene opreme i tipičan profil potrošnje. Detaljna analiza uključuje vaše stvarne '
         'račune ili podatke sa brojila, krov i orijentaciju panela, ponude za opremu, bateriju i scenarije cena, '
         'i završava se izveštajem sa preporukom.')
kontakt = f'**{KONTAKT_IME}**  \n✉️ {KONTAKT_EMAIL}' + (f'  \n📞 {KONTAKT_TELEFON}' if KONTAKT_TELEFON else '')
st.info(kontakt)

with st.expander('Pretpostavke'):
    st.write(f'''
- Paneli okrenuti ka jugu, nagib {NAGIB}°, odnos snage panela i invertora {br(DC_AC, 1)}.
- Cena elektrane ključ u ruke {CENA_SOLARA} €/kWp, održavanje {br(ODRZAVANJE * 100)} % investicije godišnje.
- Cena struje raste {br(RAST_CENE * 100)} % godišnje, paneli gube {br(DEGRADACIJA * 100, 1)} % snage godišnje, vek {VEK} godina.
- NPV uz diskontnu stopu {br(DISKONTNA_STOPA * 100)} %. Bez kredita, poreza i troškova angažovane snage.
- Potrošnja je raspoređena po satima prema izabranom radnom vremenu; van radnog vremena firma troši {br(BAZNA_UDEO * 100)} % potrošnje u radno vreme.
- Proizvodnja: tipična meteorološka godina iz PVGIS-a (Evropska komisija), model pvlib. Lokalne senke nisu uračunate.
- Rezultat je okvirna procena, a ne ponuda ni tehnički projekat.
''')
