# Question Paper Leak Detection System

A web application that finds the source of a leaked exam question paper using
**LSB steganography** and **RSA digital signatures**.

Every exam centre receives a copy of the question paper that looks identical,
but each copy carries a hidden, digitally signed identity. If a paper leaks,
uploading it to the website reveals which centre it came from, and any forgery
or editing is detected.

## Features

- Create signed copies for many exam centres at once and download them as a ZIP
- Verify a leaked copy without logging in
- Three clear results: genuine (green), tampered (yellow), no data (red)
- Detects forged centre details and edited question papers
- Admin login with hashed passwords, records page with search
- Responsive design for computer and mobile

## Technology

| Part | Technology |
|---|---|
| Steganography | LSB on PNG images (Pillow, NumPy) |
| Digital signature | RSA-1024 with PSS padding (cryptography) |
| Hashing | SHA-512 |
| Web | Flask, Jinja2, Bootstrap 5 |
| Database | SQLite |
| Testing | pytest (48 automated tests) |

## How it works

1. A SHA-512 hash of the question paper (ignoring pixel LSBs) is calculated.
2. Centre details and the hash are stored as JSON and signed with the RSA private key.
3. The JSON and the 128-byte signature are hidden in the pixel LSBs.
4. To verify, the hidden data is extracted, the signature is checked with the
   public key, and the image hash is recalculated and compared.

## Setup

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python setup_keys.py
python create_admin.py
python app.py
```

Then open http://127.0.0.1:5000

## Testing

```
python -m pytest -v
python tools/psnr.py
```

## Limitations

- Works only when the original PNG file leaks. JPG compression, WhatsApp
  "photo" sharing, cropping or printing destroys the hidden data.
- RSA-1024 is used for demonstration. Real-world use should use RSA-2048 or
  more (change `KEY_SIZE` in `crypto_utils.py`).

## Author

Sukdeb Mondal, Ramakrishna Mission Vidyamandira, belur math, 2026





<!-- 
1. Activate ENV
2. Generate KEY (python setup_keys.py)
3. admin password set (python create_admin.py)
4. start the website (python app.py)




 -->