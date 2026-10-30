CONCRETE CURING DASHBOARD — UPDATED NURSE–SAUL VERSION

Included:
- Existing Streamlit dashboard and ANN model (model file preserved unchanged)
- Nurse–Saul maturity calculation with datum temperature defaulted to -10°C
- Cube calibration inputs for measured strength AND actual cumulative maturity at each cube age
- Piecewise-linear calibration, with estimates restricted to the measured maturity range
- ANN model integration with an explicit input-feature setting (must be verified from model training code)
- Supabase persistence for cube calibration records
- ThingSpeak and CSV data sources

IMPORTANT SCIENTIFIC NOTES
1. Nurse–Saul maturity is integrated from the temperature history:
   M = sum(max(T_average - T0, 0) * delta_t)
   with T0 = -10°C by default.
2. Enter the actual cumulative maturity recorded when each 3, 7, 14, 21 and 28-day cube was tested.
   Do not use age multiplied by an assumed temperature as a substitute.
3. Cube-calibrated strength is interpolated only between measured maturity points. The app does not extrapolate
   or invent a strength when the current maturity is outside the measured range.
4. The supplied ANN model accepts one numeric input, but the model file has no feature name/training metadata.
   In Settings, leave ANN input as "Not configured" until you verify whether the model was trained using
   elapsed age (days) or maturity (°C·hr). Selecting the wrong input would produce an invalid prediction.
   Share the ANN training script or feature definition to complete that verification.

LOCAL SETUP
1. Install dependencies:
   pip install -r requirements.txt
2. Run:
   streamlit run app.py
3. For local Supabase configuration, copy secrets.example.toml to .streamlit/secrets.toml
   and enter your own project URL and secret key. Never commit real secrets.

SUPABASE SETUP
1. Open Supabase SQL Editor.
2. Run supabase_setup.sql.
3. On Render, add:
   SUPABASE_URL
   SUPABASE_SECRET_KEY
   THINGSPEAK_CHANNEL_ID
   THINGSPEAK_READ_KEY
   DISPLAY_TZ=Asia/Kolkata
4. The Supabase secret key is server-side only. Do not put it in GitHub or browser code.
5. Cube calibration data is saved to the cube_calibration table when the app has a working Supabase connection.

RENDER DEPLOYMENT
1. Replace the app files in the existing GitHub repository with this project.
2. Keep the existing ANN model file in the repository.
3. Commit and push; Render should deploy automatically.
4. Confirm the Render build installs requirements.txt successfully.
5. Create the Supabase table before saving cube calibration records.

ANN MODEL NOTE
The model was preserved. Its pickle metadata identifies one numeric input but does not identify the meaning or unit
of that input. The application intentionally does not assume that the input is maturity or age.
