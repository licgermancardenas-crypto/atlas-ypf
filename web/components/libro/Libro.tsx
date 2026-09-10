'use client';

// El módulo del libro: las cinco vistas del Excel, en el navegador.
//
// Cada pestaña baja su propio JSON la primera vez que se la abre. Los estados
// completos son 125 KB y la mayoría de las visitas mira la valuación o los
// segmentos: bajarlo todo de entrada sería hacerle pagar a cada lector una
// tabla de doscientas cincuenta líneas que quizá no abra.
//
// La pestaña activa va en el link, así que una vista se puede compartir.

import { useCallback, useEffect, useState } from 'react';

import { Esqueleto } from '@/components/Panel';
import { PanelComparables, PanelDeuda, PanelSegmentos } from '@/components/libro/Paneles';
import { PanelValuacion } from '@/components/libro/PanelValuacion';
import { TablaEstados } from '@/components/libro/TablaEstados';
import type { Comparables, Deuda, Estados, Mercado, Segmentos } from '@/lib/libro';

type Pestania = 'valuacion' | 'estados' | 'segmentos' | 'comparables' | 'deuda';

const PESTANIAS: { id: Pestania; etiqueta: string; resumen: string }[] = [
  { id: 'valuacion', etiqueta: 'Valuación', resumen: 'Cuatro métodos, supuestos a mano' },
  { id: 'estados', etiqueta: 'Estados', resumen: 'Resultados, balance y flujo' },
  { id: 'segmentos', etiqueta: 'Segmentos', resumen: 'Upstream, refino y gas' },
  { id: 'comparables', etiqueta: 'Comparables', resumen: 'Contra Vista y Pampa' },
  { id: 'deuda', etiqueta: 'Deuda', resumen: 'Escalera de vencimientos' },
];

const ARCHIVOS: Record<Exclude<Pestania, 'valuacion'>, string> = {
  estados: '/data/estados_web.json',
  segmentos: '/data/segmentos_web.json',
  comparables: '/data/comparables_web.json',
  deuda: '/data/deuda_web.json',
};

export function Libro({
  mercado,
  ypfComparable,
}: {
  mercado: Mercado;
  ypfComparable: { titulo: string; valores: Record<string, number | null> };
}) {
  const [pestania, setPestania] = useState<Pestania>('valuacion');
  const [datos, setDatos] = useState<Record<string, unknown>>({});
  const [cargando, setCargando] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // La pestaña del link manda al abrir, y se actualiza al cambiarla.
  useEffect(() => {
    const desdeElLink = new URLSearchParams(window.location.search).get('vista');
    if (desdeElLink && PESTANIAS.some((item) => item.id === desdeElLink)) {
      setPestania(desdeElLink as Pestania);
    }
  }, []);

  const cambiar = useCallback((destino: Pestania) => {
    setPestania(destino);
    const url = new URL(window.location.href);
    url.searchParams.set('vista', destino);
    window.history.replaceState(null, '', url);
  }, []);

  useEffect(() => {
    if (pestania === 'valuacion' || datos[pestania] || cargando === pestania) return;
    const archivo = ARCHIVOS[pestania];
    setCargando(pestania);
    fetch(archivo)
      .then((respuesta) => {
        if (!respuesta.ok) throw new Error(`${respuesta.status} al pedir ${archivo}`);
        return respuesta.json();
      })
      .then((contenido) => setDatos((previo) => ({ ...previo, [pestania]: contenido })))
      .catch((causa) => setError((causa as Error).message))
      .finally(() => setCargando(null));
  }, [cargando, datos, pestania]);

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {PESTANIAS.map((item) => {
          const activa = pestania === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => cambiar(item.id)}
              aria-current={activa ? 'true' : undefined}
              className={`marquesina rounded-md border px-3 py-2 text-left transition-colors ${
                activa
                  ? 'border-azul-claro bg-superficie-alta'
                  : 'border-borde hover:border-azul-claro/60'
              }`}
              data-activa={activa}
            >
              <span className={`block text-sm ${activa ? 'text-texto' : 'text-texto-suave'}`}>
                {item.etiqueta}
              </span>
              <span className="mt-0.5 block text-[0.7rem] leading-snug text-texto-tenue">
                {item.resumen}
              </span>
            </button>
          );
        })}
      </div>

      <div className="mt-6">
        {error ? (
          <div className="rounded-lg border border-borde bg-superficie p-6 text-sm text-texto-suave">
            No se pudieron cargar los datos del libro ({error}). Correr{' '}
            <code className="text-azul-claro">python pipeline/run_all.py</code> y{' '}
            <code className="text-azul-claro">npm run sync-data</code>.
          </div>
        ) : pestania === 'valuacion' ? (
          <PanelValuacion mercado={mercado} />
        ) : cargando === pestania || !datos[pestania] ? (
          <Esqueleto alto={420} />
        ) : pestania === 'estados' ? (
          <TablaEstados estados={datos.estados as Estados} />
        ) : pestania === 'segmentos' ? (
          <PanelSegmentos segmentos={datos.segmentos as Segmentos} />
        ) : pestania === 'comparables' ? (
          <PanelComparables comparables={datos.comparables as Comparables} ypf={ypfComparable} />
        ) : (
          <PanelDeuda deuda={datos.deuda as Deuda} />
        )}
      </div>
    </div>
  );
}
