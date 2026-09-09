import Link from 'next/link';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { marked } from 'marked';

// El memo vive en docs/memo_ejecutivo.md, que es el entregable del repo. Acá se
// renderiza en el build: una sola fuente de verdad, y el markdown se sigue
// pudiendo leer en GitHub sin pasar por la web.
async function memoHtml(): Promise<string> {
  const ruta = join(process.cwd(), 'public', 'memo_ejecutivo.md');
  const markdown = await readFile(ruta, 'utf-8');
  return marked.parse(markdown, { async: false, gfm: true });
}

export const metadata = {
  title: 'Memo ejecutivo — YPF 2T 2026',
  description: 'El caso YPF / Vaca Muerta en una página, en formato equity research note.',
};

export default async function Memo() {
  const html = await memoHtml();

  return (
    <main className="mx-auto max-w-3xl px-6 py-14">
      <Link
        href="/ypf-project"
        className="font-mono text-xs tracking-[0.2em] text-azul-claro transition hover:opacity-80"
      >
        ← VOLVER AL CASO
      </Link>

      {/* El markdown viene de un archivo del propio repo, no de input de nadie:
          el riesgo de inyección es el mismo que el de cualquier otro código
          fuente commiteado. */}
      <article className="memo mt-8" dangerouslySetInnerHTML={{ __html: html }} />
    </main>
  );
}
