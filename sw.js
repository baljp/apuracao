/*
 * Service worker — é o que permite instalar a página como aplicativo no
 * celular e abrir rápido mesmo com internet ruim.
 *
 * A regra importante aqui é a separação entre duas coisas:
 *
 *   o casco (HTML, scripts, base do 1º turno, ícones) nunca muda durante a
 *   noite, então fica guardado no aparelho e abre instantaneamente;
 *
 *   os dados do TSE NUNCA são guardados. Toda leitura vai direto à rede. Um
 *   aplicativo de apuração que mostra número velho em cache seria pior do que
 *   não existir.
 */

const VERSAO = "apuracao-v1";

const CASCO = [
  "./",
  "./index.html",
  "./modelo.js",
  "./tse.js",
  "./base.json",
  "./manifest.webmanifest",
  "./icone-192.png",
  "./icone-512.png",
];

self.addEventListener("install", (evento) => {
  evento.waitUntil(
    caches.open(VERSAO)
      .then((cache) => cache.addAll(CASCO))
      .then(() => self.skipWaiting())
      .catch(() => self.skipWaiting())  // falta de um arquivo não trava a instalação
  );
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches.keys()
      .then((chaves) => Promise.all(
        chaves.filter((c) => c !== VERSAO).map((c) => caches.delete(c))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (evento) => {
  const req = evento.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  // Dados do TSE: sempre da rede, nunca do cache.
  if (url.hostname.endsWith("tse.jus.br")) return;

  // Casco: responde do cache na hora e atualiza em segundo plano, para que
  // uma correção publicada chegue na próxima abertura.
  evento.respondWith(
    caches.match(req).then((guardado) => {
      const daRede = fetch(req).then((resp) => {
        if (resp && resp.ok && url.origin === self.location.origin) {
          const copia = resp.clone();
          caches.open(VERSAO).then((cache) => cache.put(req, copia));
        }
        return resp;
      }).catch(() => guardado);
      return guardado || daRede;
    })
  );
});
