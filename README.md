# svjetovi-znanja

Svjetovi znanja je edukativna AI-temeljena MMORPG igra implementirana u sklopu kolegija Odabrana poglavlja umjetne inteligencije na poslijediplomskom doktorskom studiju "Informacijske znanosti" i Laboratorija za umjetnu inteligenciju na Fakultetu organizacije i informatike.

# Implementacija

Implementacija se temelji na [(MMO)RPG Maker MV](https://github.com/samuelcardillo/MMORPGMaker-MV). Igra je implementirana u alatu [RPG Maker MV](https://www.rpgmakerweb.com/products/rpg-maker-mv), Pythonu i bash skriptama.

# Instalacija

Za instalaciju potrebno je:

1. Klonirati ovaj repozitorij `git clone https://github.com/AILab-FOI/svjetovi-znanja.git`
2. Instalirati [NodeJS](https://nodejs.org/en/) te pokrenuti `npm i` u `server` poddirektoriju
3. Instalirati [RethinkDB](https://rethinkdb.com/docs/install/)
4. Instalirati potrebne Python pakete `pip install -r requirements.txt`

# Pokretanje

Prije pokretanja potrebno je otvoriti datoteku projekta (`Game.rpgproject`) u alatu [RPG Maker MV](https://www.rpgmakerweb.com/products/rpg-maker-mv) te generirati produkcijsku inačicu igre za Web sučelje. U meniju odabrati `File > Deployment ...` zatim pod `Platform` odabrati `Web browsers` i sa `Choose...` odabrati lokaciju gdje će se instanca pohraniti (oprez, treba biti izvan direktorija sa izvornim kodom). Nakon toga odabrati `OK`.

Nakon što se izgenerira instanca, pozicionirati se u prethodno odabrani direktorij i u ljusci pokrenuti `run.sh` (ako koristite Linux). Skripta će vas tražiti ključ za [OpenAI API](https://platform.openai.com/api-keys). Nakon što unesete ključ, pritisnite enter i trebao bi se pokrenuti poslužitelj baze podataka, MMO poslužitelj i Web poslužitelj.

Ukoliko ne koristite Linux, potrebno je ručno učiniti sljedeće:
- U varijablu okružja (engl. environment variable) `OPENAI_API_KEY` zapisati vaš OpenAI API ključ.
- U direktoriju `server` pokrenuti `rethinkdb`.
- U direktoriju `server` pokrenutu `node mmo.js`.
- U direktoriju `server` pokrenuti `python3 openai-server.py`

Ako je sve bilo uspješno, igra je dostupna na adresi `localhost:5000` u web pregledniku.

# Napomene o licenciranju

Korištena grafika, audio, video i sav ostali materijal iz alata RPG Maker MV kao i programski kod koji je dio stroja igre ili dodataka licenciran je pod komercijalnom licencom. Za korištenje potrebno je kupiti [RPG Maker MV](https://www.rpgmakerweb.com/products/rpg-maker-mv) alat zajedno sa svim potrbnim dodacima.


