import type { Metadata } from 'next';
import { Archivo, IBM_Plex_Mono, IBM_Plex_Sans } from 'next/font/google';
import './globals.css';

// Tres roles, tres familias. Archivo es una grotesca ancha y con peso: sostiene
// titulares sin recurrir a la serif de alto contraste que hoy usa todo el mundo.
// IBM Plex es la tipografía de ingeniería de IBM, que es exactamente el registro
// de este documento —pozos, barriles, modelos— y su versión mono hace legible la
// columna de números, que en esta página es la mitad del contenido.
const display = Archivo({
  subsets: ['latin'],
  weight: ['600', '700'],
  variable: '--fuente-display',
  display: 'swap',
});

const sans = IBM_Plex_Sans({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--fuente-sans',
  display: 'swap',
});

const mono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--fuente-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'ATLAS-YPF — Por qué el mercado castigó el balance récord',
  description:
    'Caso de estudio sobre YPF y Vaca Muerta: financieros, producción por pozo, ' +
    'economía de pozo, reacción del mercado y simulador de escenarios.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={`${display.variable} ${sans.variable} ${mono.variable}`}>
      <body className="min-h-screen antialiased">
        {/* Primer elemento enfocable de la página: quien navega con teclado no
            tiene por qué recorrer la barra de secciones en cada carga. */}
        <a
          href="#balance"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-azul focus:px-4 focus:py-2 focus:text-sm focus:text-white"
        >
          Saltar al contenido
        </a>
        {children}
      </body>
    </html>
  );
}
