'use client';

// El mapa de la cuenca. deck.gl sin basemap de terceros: el fondo es el
// hillshade que genera pipeline/transform/geo_layers.py, así que la página no
// depende de un token de Mapbox ni de que un tile server siga vivo dentro de dos
// años. Todo lo que se ve sale de data/processed/geo/.

import { useEffect, useMemo, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { BitmapLayer, GeoJsonLayer, ScatterplotLayer } from '@deck.gl/layers';
import type { PickingInfo } from '@deck.gl/core';

import { fmt } from '@/lib/data';

interface Raster {
  bounds: [number, number, number, number];
  elevacion_min_m: number;
  elevacion_max_m: number;
  fuente: string;
}

interface PropiedadesPozo {
  sigla: string;
  operador: string;
  yacimiento: string;
  es_vaca_muerta: boolean;
  boe_acum_mboe: number;
  eur_mbbl: number | null;
  npv_musd: number | null;
  breakeven_brent: number | null;
  anio_inicio: number | null;
}

type Pozo = { coordinates: [number, number]; propiedades: PropiedadesPozo };

type Coloreo = 'volumen' | 'valor';

const VISTA_INICIAL = {
  longitude: -69.2,
  latitude: -38.4,
  zoom: 6.6,
  pitch: 40,
  bearing: -15,
};

// Escala de volumen: ámbar creciente. Escala de valor: rojo para el pozo que no
// repaga el capex de hoy, verde para el que sí. Son dos preguntas distintas y
// por eso son dos escalas, no una con doble sentido.
const RAMPA_VOLUMEN: [number, number, number][] = [
  [90, 70, 50],
  [150, 100, 45],
  [205, 135, 45],
  [240, 175, 60],
  [255, 215, 120],
];

function colorVolumen(mboe: number): [number, number, number] {
  const indice = Math.min(Math.floor(Math.log10(Math.max(mboe, 1)) * 1.6), RAMPA_VOLUMEN.length - 1);
  return RAMPA_VOLUMEN[Math.max(indice, 0)];
}

function colorValor(npv: number | null): [number, number, number] {
  if (npv === null) return [110, 110, 120];
  if (npv < 0) return [214, 96, 77];
  if (npv < 10) return [230, 175, 90];
  if (npv < 25) return [140, 200, 130];
  return [80, 200, 140];
}

export function MapaPozos() {
  const [pozos, setPozos] = useState<Pozo[] | null>(null);
  const [concesiones, setConcesiones] = useState<unknown>(null);
  const [cuenca, setCuenca] = useState<unknown>(null);
  const [raster, setRaster] = useState<Raster | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [coloreo, setColoreo] = useState<Coloreo>('volumen');
  const [soloVacaMuerta, setSoloVacaMuerta] = useState(true);
  const [señalado, setSeñalado] = useState<PickingInfo<Pozo> | null>(null);

  useEffect(() => {
    let vigente = true;

    async function cargar() {
      try {
        const [pozosGeo, concesionesGeo, cuencaGeo, rasterJson] = await Promise.all([
          fetch('/data/geo/wells.geojson').then((r) => r.json()),
          fetch('/data/geo/concessions.geojson').then((r) => r.json()),
          fetch('/data/geo/basin.geojson').then((r) => r.json()),
          fetch('/data/geo/raster.json').then((r) => r.json()),
        ]);
        if (!vigente) return;

        setPozos(
          pozosGeo.features.map(
            (feature: {
              geometry: { coordinates: [number, number] };
              properties: PropiedadesPozo;
            }) => ({
              coordinates: feature.geometry.coordinates,
              propiedades: feature.properties,
            }),
          ),
        );
        setConcesiones(concesionesGeo);
        setCuenca(cuencaGeo);
        setRaster(rasterJson);
      } catch (causa) {
        if (vigente) setError((causa as Error).message);
      }
    }

    cargar();
    return () => {
      vigente = false;
    };
  }, []);

  const visibles = useMemo(
    () => (pozos ?? []).filter((pozo) => (soloVacaMuerta ? pozo.propiedades.es_vaca_muerta : true)),
    [pozos, soloVacaMuerta],
  );

  const capas = useMemo(() => {
    const lista = [];

    if (raster) {
      lista.push(
        new BitmapLayer({
          id: 'relieve',
          image: '/data/geo/hillshade.png',
          bounds: raster.bounds,
          opacity: 0.55,
        }),
      );
    }
    if (cuenca) {
      lista.push(
        new GeoJsonLayer({
          id: 'cuenca',
          data: cuenca as never,
          stroked: true,
          filled: true,
          getFillColor: [40, 120, 150, 30],
          getLineColor: [110, 190, 220, 160],
          lineWidthMinPixels: 1.5,
        }),
      );
    }
    if (concesiones) {
      lista.push(
        new GeoJsonLayer({
          id: 'concesiones',
          data: concesiones as never,
          stroked: true,
          filled: true,
          getFillColor: [200, 140, 60, 25],
          getLineColor: [220, 160, 80, 130],
          lineWidthMinPixels: 0.8,
          pickable: false,
        }),
      );
    }
    if (visibles.length) {
      lista.push(
        new ScatterplotLayer<Pozo>({
          id: 'pozos',
          data: visibles,
          getPosition: (pozo) => pozo.coordinates,
          // El radio va por la raíz de la acumulada: si fuera lineal, tres pozos
          // gigantes taparían la cuenca entera.
          getRadius: (pozo) => 300 + Math.sqrt(Math.max(pozo.propiedades.boe_acum_mboe, 0)) * 55,
          getFillColor: (pozo) =>
            coloreo === 'volumen'
              ? colorVolumen(pozo.propiedades.boe_acum_mboe)
              : colorValor(pozo.propiedades.npv_musd),
          radiusMinPixels: 1.5,
          radiusMaxPixels: 22,
          opacity: 0.85,
          pickable: true,
          onHover: (info) => setSeñalado(info.object ? info : null),
          updateTriggers: { getFillColor: [coloreo] },
        }),
      );
    }
    return lista;
  }, [raster, cuenca, concesiones, visibles, coloreo]);

  if (error) {
    return (
      <div className="rounded-xl border border-borde bg-superficie p-6 text-sm text-texto-suave">
        No se pudieron cargar las capas del mapa ({error}). Correr{' '}
        <code className="text-azul-claro">python pipeline/run_all.py</code> y{' '}
        <code className="text-azul-claro">npm run sync-data</code>.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-borde bg-superficie">
      <div className="flex flex-wrap items-center gap-3 border-b border-borde px-4 py-3">
        <div className="flex rounded-lg border border-borde p-0.5">
          {(['volumen', 'valor'] as const).map((modo) => (
            <button
              key={modo}
              type="button"
              onClick={() => setColoreo(modo)}
              className={`rounded-md px-3 py-1 text-xs transition ${
                coloreo === modo
                  ? 'bg-superficie-alta text-azul-claro'
                  : 'text-texto-suave hover:text-texto'
              }`}
            >
              {modo === 'volumen' ? 'Color por acumulada' : 'Color por NPV'}
            </button>
          ))}
        </div>

        <label className="flex items-center gap-2 text-xs text-texto-suave">
          <input
            type="checkbox"
            checked={soloVacaMuerta}
            onChange={(evento) => setSoloVacaMuerta(evento.target.checked)}
            className="accent-[#0063be]"
          />
          Solo Vaca Muerta
        </label>

        <span className="tabular ml-auto text-xs text-texto-tenue">
          {pozos ? `${fmt.entero(visibles.length)} pozos` : 'cargando capas…'}
        </span>
      </div>

      <div className="relative h-[540px] w-full">
        <DeckGL
          initialViewState={VISTA_INICIAL}
          controller
          layers={capas}
          style={{ position: 'absolute', inset: '0' }}
        />

        {señalado?.object ? (
          <div
            className="pointer-events-none absolute z-10 w-60 rounded-lg border border-borde bg-fondo/95 p-3 text-xs shadow-xl"
            style={{ left: (señalado.x ?? 0) + 12, top: (señalado.y ?? 0) + 12 }}
          >
            <p className="font-medium text-texto">{señalado.object.propiedades.sigla}</p>
            <p className="mt-0.5 text-texto-tenue">
              {señalado.object.propiedades.operador} · {señalado.object.propiedades.yacimiento}
            </p>
            <dl className="tabular mt-2 space-y-1 text-texto-suave">
              <div className="flex justify-between gap-3">
                <dt>Acumulada</dt>
                <dd>{fmt.decimal(señalado.object.propiedades.boe_acum_mboe)} Mboe</dd>
              </div>
              {señalado.object.propiedades.eur_mbbl !== null ? (
                <div className="flex justify-between gap-3">
                  <dt>EUR</dt>
                  <dd>{fmt.decimal(señalado.object.propiedades.eur_mbbl)} Mbbl</dd>
                </div>
              ) : null}
              {señalado.object.propiedades.npv_musd !== null ? (
                <div className="flex justify-between gap-3">
                  <dt>NPV</dt>
                  <dd
                    className={
                      señalado.object.propiedades.npv_musd >= 0 ? 'text-alza' : 'text-baja'
                    }
                  >
                    US$ {fmt.decimal(señalado.object.propiedades.npv_musd)}M
                  </dd>
                </div>
              ) : null}
              {señalado.object.propiedades.anio_inicio !== null ? (
                <div className="flex justify-between gap-3">
                  <dt>Primera producción</dt>
                  <dd>{señalado.object.propiedades.anio_inicio}</dd>
                </div>
              ) : null}
            </dl>
          </div>
        ) : null}
      </div>

      <p className="border-t border-borde px-4 py-3 text-xs leading-relaxed text-texto-tenue">
        Relieve: {raster?.fuente ?? 'Copernicus DEM GLO-30'}. Concesiones y pozos: Secretaría de
        Energía. El NPV es el del pozo evaluado como si se perforara hoy con los supuestos del caso,
        así que un pozo viejo con NPV negativo no significa que haya dado pérdida: significa que no
        repagaría el capex de hoy.
      </p>
    </div>
  );
}
