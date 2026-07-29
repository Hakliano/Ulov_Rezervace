# Owner FLOW + heslo (salon2 jako vzor)

Schválené chování majitele žije v **`shared/owner-flow-admin.js`**.  
Backend už je společný: `POST /api/salon/<id>/flow/aktivace/` + `ensure_owner_flow_user`.

## Povinné zapojení u každého partner webu

1. V `index.html` před `app.js`:
   ```html
   <script src="../shared/owner-flow-admin.js"></script>
   <script src="app.js"></script>
   ```
2. V `app.js` hned po `SALON_ID`:
   ```js
   window.UlovOwnerFlowConfig = {
     getSalonId: () => SALON_ID,
     getApiBase: () => API_BASE,
     getToken: () => staffToken,
     isMajitel: () => isMajitel(),
     getEmail: () => (
       document.getElementById('staff-login')?.value
       || staffUser?.prihlasovaci_jmeno
       || staffUser?.email
       || ''
     ).trim(),
   };
   ```
3. Po úspěšném přihlášení majitele (když se ukáže `#edit-section`):
   ```js
   window.UlovOwnerFlow?.onAdminShown?.();
   ```

Modul sám doplní box **Přejít do FLOW** (záložka Základ) a záložku **Heslo**.

## Checklist nového pro partnera

1. DB salon + majitel (e-mail login) + `seed_rezervace`
2. Statická složka webu s `SALON_ID` + výše uvedené 3 body
3. Deploy `shared/owner-flow-admin.js` spolu s webem (`www/shared/` / `www-staging/shared/`)
4. Smoke: ⚙ → přihlášení → **Přejít do FLOW** → login ve FLOW stejným e-mailem/heslem
5. Partner-admin zůstává záložní cesta aktivace (ops)

## Co nedělat

- Nekopírovat FLOW handler ručně ze salon2 do dalšího dema — vždy shared modul.
- Nenasazovat partner web bez `shared/` (jinak chybí vstup do FLOW).
