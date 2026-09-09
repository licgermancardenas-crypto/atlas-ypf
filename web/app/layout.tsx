import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'ATLAS-YPF — Por qué el mercado castigó el balance récord',
  description:
    'Caso de estudio sobre YPF y Vaca Muerta: financieros, producción por pozo, ' +
    'economía de pozo, reacción del mercado y simulador de escenarios.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
