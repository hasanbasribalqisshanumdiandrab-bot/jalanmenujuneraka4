/**
 * putusan.js  --  FILE BARU, taruh sejajar index.html di repo GitHub Pages.
 *
 * LANGKAH PASANG
 * 1. Di index.html, sebelum </body>, tambahkan:
 *      <script src="putusan.js"></script>
 * 2. Isi APPS_SCRIPT_URL di bawah dengan URL Web App (/exec) kamu.
 * 3. Di fungsi pencarian lama, SESUDAH hasil pencarian tampil, panggil:
 *
 *      Putusan.jalankan(teksSoalAsli, hasilTeratas, document.getElementById('hasil'));
 *
 *    - teksSoalAsli : isi kotak soal (mentah, sebelum dibersihkan)
 *    - hasilTeratas : array hasil pencarian terurut skor, tiap item
 *                     { file:'photo_32...', hal:1, teks:'teks OCR halaman' }
 *                     (sesuaikan nama field dengan hasil pencarianmu)
 *    - elemen hasil : container tempat kartu disisipkan di paling atas
 */
(function () {
  var APPS_SCRIPT_URL = 'GANTI_DENGAN_URL_EXEC_APPS_SCRIPT';

  function bersihkanSoal(t) {
    return String(t || '')
      .replace(/[\uFFFC\uFFFD\u200B]/g, ' ')
      .replace(/\bQuestion\s*\d+\s*Answer\b/gi, ' ')
      .replace(/\b(True|False|Benar|Salah)\b\s*$/gim, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function soalBenarSalah(raw) {
    raw = String(raw || '');
    return (/\bTrue\b/i.test(raw) && /\bFalse\b/i.test(raw)) ||
           (/\bBenar\b/i.test(raw) && /\bSalah\b/i.test(raw));
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function kartu(container, html, warna) {
    var el = document.getElementById('kartu-putusan');
    if (!el) {
      el = document.createElement('div');
      el.id = 'kartu-putusan';
      container.insertBefore(el, container.firstChild);
    }
    el.style.cssText =
      'margin:0 0 14px;padding:14px 16px;border-radius:12px;border:1px solid ' + warna +
      ';background:' + warna + '22;color:inherit;line-height:1.5';
    el.innerHTML = html;
  }

  async function jalankan(soalMentah, hasil, container) {
    if (!soalBenarSalah(soalMentah)) return;          // bukan soal benar/salah
    container = container || document.body;
    var soal = bersihkanSoal(soalMentah);
    var potongan = (hasil || []).slice(0, 3);
    if (!potongan.length) {
      kartu(container, '<b>Perlu dicek manual</b> — materi tidak ditemukan.', '#f59e0b');
      return;
    }

    kartu(container, '⏳ Menyimpulkan True/False dari materi…', '#64748b');

    try {
      var r = await fetch(APPS_SCRIPT_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'text/plain;charset=utf-8' },  // hindari preflight CORS
        body: JSON.stringify({ aksi: 'putusan', soal: soal, potongan: potongan })
      });
      var data = await r.json();
      if (!data.ok) throw new Error(data.error || 'Gagal');
      var h = data.hasil || {};
      var j = String(h.jawaban || '').toUpperCase();

      var judul, warna;
      if (j === 'TRUE')       { judul = '✅ TRUE';  warna = '#16a34a'; }
      else if (j === 'FALSE') { judul = '❌ FALSE'; warna = '#dc2626'; }
      else                    { judul = '⚠️ Perlu dicek manual'; warna = '#f59e0b'; }

      kartu(container,
        '<div style="font-size:1.25rem;font-weight:800">' + judul + '</div>' +
        (h.alasan ? '<div style="margin-top:6px">' + esc(h.alasan) + '</div>' : '') +
        (h.kutipan ? '<div style="margin-top:6px;opacity:.85;font-style:italic">“' + esc(h.kutipan) + '”</div>' : '') +
        (h.sumber ? '<div style="margin-top:6px;font-size:.8rem;opacity:.7">Sumber: ' + esc(h.sumber) + '</div>' : '') +
        '<div style="margin-top:6px;font-size:.75rem;opacity:.6">Hasil OCR bisa keliru — cek gambar halaman bila ragu.</div>',
        warna);
    } catch (e) {
      kartu(container, '⚠️ Gagal menyimpulkan: ' + esc(e.message), '#f59e0b');
    }
  }

  window.Putusan = { jalankan: jalankan, bersihkanSoal: bersihkanSoal, soalBenarSalah: soalBenarSalah };
})();
