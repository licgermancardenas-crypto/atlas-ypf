import { ImageResponse } from 'next/og';

import { cargar } from '@/lib/server-data';
import { fmt, type Financieros, type Mercado } from '@/lib/data';

// La tarjeta que se ve cuando alguien comparte el link.
//
// Hasta acá el caso se compartía como una tarjeta vacía, que en un trabajo de
// portfolio es desperdiciar el momento exacto en que a alguien le llega el
// link. Muestra la tesis entera: los dos números en tensión.
//
// Se genera en el build y no por request: los números salen del pipeline y solo
// cambian cuando cambia el dato, así que servirla estática es gratis.
//
// Sobre el markup: lo dibuja Satori, no un navegador. No hereda estilos como el
// CSS normal y exige `display: flex` explícito en todo div con más de un hijo,
// así que acá cada bloque es o un texto solo o un contenedor flex declarado.

export const alt =
  'YPF publicó el mejor trimestre de su historia y la acción cayó el mismo día';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

const COLOR = {
  fondo: '#000d2d',
  borde: '#172c5c',
  azul: '#0054eb',
  azulClaro: '#4d90ff',
  celeste: '#75aadb',
  oro: '#f0a830',
  baja: '#e2603f',
  texto: '#eef3ff',
  suave: '#a8b8d8',
  tenue: '#6d80a8',
};

function Cifra({ etiqueta, valor, color }: { etiqueta: string; valor: string; color: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <div style={{ fontSize: 20, color: COLOR.tenue, letterSpacing: 2 }}>{etiqueta}</div>
      <div style={{ fontSize: 96, fontWeight: 700, color }}>{valor}</div>
    </div>
  );
}

export default async function Imagen() {
  const financieros = await cargar<Financieros>('financials_ypf.json');
  const mercado = await cargar<Mercado>('market_reaction.json');

  const ultimo = financieros.serie[financieros.serie.length - 1];
  const previoAnual = financieros.serie[financieros.serie.length - 5];
  const evento = mercado.eventos[mercado.eventos.length - 1];

  const crecimiento =
    ultimo.adj_ebitda_musd && previoAnual.adj_ebitda_musd
      ? ultimo.adj_ebitda_musd / previoAnual.adj_ebitda_musd - 1
      : 0;

  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          background: COLOR.fondo,
          padding: '64px 72px',
          color: COLOR.texto,
          fontFamily: 'sans-serif',
        }}
      >
        {/* La franja del logo anterior a 2008, el mismo elemento que separa las
            secciones de la página. */}
        <div style={{ display: 'flex', height: 6, width: 160 }}>
          <div style={{ display: 'flex', flex: 1, background: COLOR.azul }} />
          <div style={{ display: 'flex', flex: 1, background: COLOR.celeste }} />
          <div style={{ display: 'flex', flex: 1, background: COLOR.oro }} />
        </div>

        <div style={{ marginTop: 28, fontSize: 22, letterSpacing: 4, color: COLOR.azulClaro }}>
          {`ATLAS-YPF · CASO DE ESTUDIO · ${fmt.trimestre(ultimo.trimestre).replace(/T(\d{4})/, 'T $1')}`}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', marginTop: 20 }}>
          <div style={{ fontSize: 46, fontWeight: 700, lineHeight: 1.14 }}>
            YPF publicó el mejor trimestre de su historia.
          </div>
          <div style={{ fontSize: 46, fontWeight: 700, lineHeight: 1.14, color: COLOR.suave }}>
            El mercado lo vendió.
          </div>
        </div>

        {/* El margen fijo además del auto: con el titular en tres líneas el auto
            queda en cero y las cifras se pegan al texto. */}
        <div style={{ display: 'flex', marginTop: 'auto', paddingTop: 34, alignItems: 'flex-end' }}>
          <Cifra
            etiqueta="EBITDA AJUSTADO, INTERANUAL"
            valor={fmt.porcentajeConSigno(crecimiento, 0)}
            color={COLOR.azulClaro}
          />
          <div
            style={{
              display: 'flex',
              width: 1,
              height: 130,
              background: COLOR.borde,
              margin: '0 56px',
            }}
          />
          <Cifra
            etiqueta="LA ACCIÓN, ESE MISMO DÍA"
            valor={fmt.porcentajeConSigno(evento.retorno_dia, 1)}
            color={COLOR.baja}
          />
        </div>

        <div
          style={{
            marginTop: 36,
            paddingTop: 20,
            borderTop: `1px solid ${COLOR.borde}`,
            fontSize: 19,
            color: COLOR.tenue,
          }}
        >
          SEC EDGAR · Secretaría de Energía · EMBI+ Argentina — atlas-ypf.vercel.app
        </div>
      </div>
    ),
    size,
  );
}
