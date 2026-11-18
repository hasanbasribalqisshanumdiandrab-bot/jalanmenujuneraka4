/**
 * Putusan.gs  --  FILE BARU di project Apps Script (tambahkan, jangan hapus file lama)
 *
 * LANGKAH PASANG
 * 1. Apps Script > Project Settings > Script Properties > tambah:
 *      ANTHROPIC_KEY = (API key kamu)
 * 2. Di doPost(e) milik Code.gs lama, taruh BARIS INI paling atas:
 *      if (e && e.postData && e.postData.contents.indexOf('"aksi":"putusan"') > -1) return handlePutusan(e);
 * 3. Deploy > Manage deployments > Edit > Version: New version > Deploy.
 */

var MODEL_PUTUSAN = 'claude-sonnet-5-5';

function handlePutusan(e) {
  var out;
  try {
    var req = JSON.parse(e.postData.contents);
    var soal = String(req.soal || '').slice(0, 1500);
    var potongan = (req.potongan || []).slice(0, 3);
    if (!soal || !potongan.length) throw new Error('Soal/materi kosong');
    out = { ok: true, hasil: putusanBenarSalah_(soal, potongan) };
  } catch (err) {
    out = { ok: false, error: String(err && err.message || err) };
  }
  return ContentService.createTextOutput(JSON.stringify(out))
    .setMimeType(ContentService.MimeType.JSON);
}

function putusanBenarSalah_(soal, potongan) {
  var materi = potongan.map(function (p, i) {
    return '[' + (i + 1) + '] (' + p.file + ' hal.' + p.hal + ') ' + String(p.teks || '').slice(0, 2500);
  }).join('\n\n');

  var prompt =
    'Kamu penilai soal Benar/Salah. Gunakan HANYA materi di bawah.\n' +
    'Jika materi tidak cukup untuk memutuskan, jawab "TIDAK_PASTI".\n' +
    'Teks OCR bisa keliru, hati-hati dengan angka dan istilah.\n\n' +
    'PERNYATAAN: ' + soal + '\n\nMATERI:\n' + materi + '\n\n' +
    'Balas JSON saja tanpa teks lain:\n' +
    '{"jawaban":"TRUE|FALSE|TIDAK_PASTI","alasan":"1-2 kalimat","kutipan":"kalimat pendukung singkat dari materi","sumber":"nama file hal."}';

  var res = UrlFetchApp.fetch('https://api.anthropic.com/v1/messages', {
    method: 'post',
    contentType: 'application/json',
    headers: {
      'x-api-key': PropertiesService.getScriptProperties().getProperty('ANTHROPIC_KEY'),
      'anthropic-version': '2023-06-01'
    },
    payload: JSON.stringify({
      model: MODEL_PUTUSAN,
      max_tokens: 400,
      messages: [{ role: 'user', content: prompt }]
    }),
    muteHttpExceptions: true
  });

  var body = JSON.parse(res.getContentText());
  if (!body.content) throw new Error((body.error && body.error.message) || 'Respons AI kosong');
  var txt = body.content.map(function (c) { return c.text || ''; }).join('')
    .replace(/```json|```/g, '').trim();
  return JSON.parse(txt);
}
