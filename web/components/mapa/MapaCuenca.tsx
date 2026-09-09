'use client';

// El mapa de la cuenca. deck.gl sin basemap de terceros: el fondo es el
// hillshade que genera el pipeline, así que la página no depende de un token de
// Mapbox ni de que un tile server siga vivo dentro de dos años.
//
// Las capas se bajan cuando se encienden, no al abrir: entre pozos, ductos y
// ríos son casi ocho megas, y cargar todo de entrada para que la mayoría quede
// apagado es hacerle pagar al lector una información que no pidió. El peso de
// cada capa está a la vista en el panel, al lado del interruptor.

import { useCallback, useEffect, useMemo, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { BitmapLayer, GeoJsonLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers';
import type { Layer, PickingInfo } from '@deck.gl/core';

import { fmt } from '@/lib/data';
import {
  CAPAS,
  CAPAS_INICIALES,
  PALETA,
  VARIABLES,
  colorEscala,
  cortes,
  type IdCapa,
  type IdVariable,
  type RGB,
} from './capas';

type Coleccion = { type: 'FeatureCollection'; features: Feature[] };
// deck.gl le pasa a los accessors de GeoJsonLayer su propio tipo de Feature, con
// la geometría tipada de GeoJSON. Para esas funciones alcanza con lo único que
// se lee —las propiedades— y así no hay que pelearse con dos definiciones del
// mismo objeto.
type ConPropiedades = { properties: Record<string, unknown> };
type Feature = {
  geometry: { type: string; coordinates: unknown };
  properties: Record<string, unknown>;
};

interface Raster {
  bounds: [number, number, number, number];
  fuente: string;
}

type PintadoPozos = 'volumen' | 'valor' | 'antiguedad';

const VISTA_INICIAL = { longitude: -69.1, latitude: -38.3, zoom: 6.7, pitch: 45, bearing: -17 };

const PINTADOS: { id: PintadoPozos; etiqueta: string }[] = [
  { id: 'volumen', etiqueta: 'Acumulada' },
  { id: 'valor', etiqueta: 'NPV' },
  { id: 'antiguedad', etiqueta: 'Año' },
];

function colorPozo(propiedades: Record<string, unknown>, modo: PintadoPozos): RGB {
  if (modo === 'valor') {
    const npv = propiedades.npv_musd as number | null;
    if (npv === null || npv === undefined) return [90, 100, 130];
    if (npv < 0) return PALETA.baja;
    if (npv < 10) return PALETA.oro;
    return PALETA.alza;
  }
  if (modo === 'antiguedad') {
    const anio = (propiedades.anio_inicio as number) ?? 2013;
    const t = Math.min(Math.max((anio - 2012) / 14, 0), 1);
    return [Math.round(20 + 57 * t), Math.round(60 + 84 * t), Math.round(120 + 135 * t)];
  }
  const mboe = (propiedades.boe_acum_mboe as number) ?? 0;
  const t = Math.min(Math.log10(Math.max(mboe, 1)) / 3.2, 1);
  return [Math.round(120 + 120 * t), Math.round(90 + 78 * t), Math.round(40 + 8 * t)];
}

export function MapaCuenca() {
  const [activas, setActivas] = useState<Set<IdCapa>>(new Set(CAPAS_INICIALES));
  const [datos, setDatos] = useState<Record<string, Coleccion>>({});
  const [cargando, setCargando] = useState<Set<string>>(new Set());
  const [raster, setRaster] = useState<Raster | null>(null);
  const [variable, setVariable] = useState<IdVariable>('boe_acum_mboe');
  const [pintado, setPintado] = useState<PintadoPozos>('volumen');
  const [operador, setOperador] = useState<string>('todos');
  const [soloVacaMuerta, setSoloVacaMuerta] = useState(false);
  const [desdeAnio, setDesdeAnio] = useState(2006);
  const [señalado, setSeñalado] = useState<PickingInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  // --- carga perezosa -------------------------------------------------------
  useEffect(() => {
    fetch('/data/geo/raster.json')
      .then((r) => r.json())
      .then(setRaster)
      .catch((causa) => setError((causa as Error).message));
  }, []);

  useEffect(() => {
    const pendientes = CAPAS.filter(
      (capa) => capa.archivo && activas.has(capa.id) && !datos[capa.archivo] && !cargando.has(capa.archivo),
    );
    if (!pendientes.length) return;

    setCargando((previo) => new Set([...previo, ...pendientes.map((c) => c.archivo!)]));
    for (const capa of pendientes) {
      fetch(`/data/geo/${capa.archivo}`)
        .then((r) => r.json())
        .then((coleccion: Coleccion) =>
          setDatos((previo) => ({ ...previo, [capa.archivo!]: coleccion })),
        )
        .catch((causa) => setError((causa as Error).message))
        .finally(() =>
          setCargando((previo) => {
            const copia = new Set(previo);
            copia.delete(capa.archivo!);
            return copia;
          }),
        );
    }
  }, [activas, datos, cargando]);

  const alternar = useCallback((id: IdCapa) => {
    setActivas((previo) => {
      const copia = new Set(previo);
      if (copia.has(id)) copia.delete(id);
      else copia.add(id);
      return copia;
    });
  }, []);

  // --- pozos filtrados ------------------------------------------------------
  const pozosCrudos = datos['wells.geojson']?.features ?? [];

  const operadores = useMemo(() => {
    const cuenta = new Map<string, number>();
    for (const pozo of pozosCrudos) {
      const nombre = (pozo.properties.operador as string) ?? 'Sin dato';
      cuenta.set(nombre, (cuenta.get(nombre) ?? 0) + 1);
    }
    return [...cuenta.entries()].sort((a, b) => b[1] - a[1]).slice(0, 14);
  }, [pozosCrudos]);

  const pozos = useMemo(
    () =>
      pozosCrudos.filter((pozo) => {
        const p = pozo.properties;
        if (operador !== 'todos' && p.operador !== operador) return false;
        if (soloVacaMuerta && !p.es_vaca_muerta) return false;
        const anio = p.anio_inicio as number | null;
        if (desdeAnio > 2006 && (anio === null || anio === undefined || anio < desdeAnio)) return false;
        return true;
      }),
    [pozosCrudos, operador, soloVacaMuerta, desdeAnio],
  );

  // --- coroplético ----------------------------------------------------------
  const definicionVariable = VARIABLES.find((v) => v.id === variable)!;
  const archivoPoligonos = activas.has('yacimientos')
    ? 'fields.geojson'
    : activas.has('concesiones')
      ? 'concessions.geojson'
      : null;

  const quiebres = useMemo(() => {
    if (!archivoPoligonos) return [];
    const valores = (datos[archivoPoligonos]?.features ?? [])
      .map((f) => f.properties[variable] as number)
      .filter((v) => Number.isFinite(v) && (variable === 'npv_musd_mediano' || v > 0));
    return cortes(valores);
  }, [datos, archivoPoligonos, variable]);

  const pintarPoligono = useCallback(
    (feature: ConPropiedades): RGB => {
      const valor = feature.properties[variable] as number | null;
      const tienePozos = ((feature.properties.pozos as number) ?? 0) > 0;
      if (!tienePozos) return [22, 34, 62];
      return colorEscala(valor, quiebres, Boolean(definicionVariable.divergente));
    },
    [variable, quiebres, definicionVariable],
  );

  // --- capas de deck.gl -----------------------------------------------------
  const capas = useMemo(() => {
    const lista: Layer[] = [];
    const encendida = (id: IdCapa) => activas.has(id);
    const coleccion = (archivo: string) => datos[archivo];

    if (encendida('relieve') && raster) {
      lista.push(
        new BitmapLayer({
          id: 'relieve',
          image: '/data/geo/hillshade.png',
          bounds: raster.bounds,
          opacity: 0.5,
        }),
      );
    }
    if (encendida('provincias') && coleccion('provinces.geojson')) {
      lista.push(
        new GeoJsonLayer({
          id: 'provincias',
          data: coleccion('provinces.geojson') as never,
          stroked: true,
          filled: false,
          getLineColor: [95, 112, 153, 110],
          lineWidthMinPixels: 1,
        }),
      );
    }
    if (encendida('cuenca') && coleccion('basin.geojson')) {
      lista.push(
        new GeoJsonLayer({
          id: 'cuenca',
          data: coleccion('basin.geojson') as never,
          stroked: true,
          filled: true,
          getFillColor: [17, 42, 197, 26],
          getLineColor: [117, 170, 219, 170],
          lineWidthMinPixels: 1.5,
        }),
      );
    }

    for (const [id, archivo] of [
      ['concesiones', 'concessions.geojson'],
      ['yacimientos', 'fields.geojson'],
    ] as const) {
      if (!encendida(id) || !coleccion(archivo)) continue;
      lista.push(
        new GeoJsonLayer({
          id,
          data: coleccion(archivo) as never,
          stroked: true,
          filled: true,
          getFillColor: (f: ConPropiedades) =>
            [...pintarPoligono(f), 165] as [number, number, number, number],
          getLineColor: [77, 144, 255, 120],
          lineWidthMinPixels: 0.7,
          pickable: true,
          onHover: (info) => setSeñalado(info.object ? { ...info, layer: info.layer } : null),
          updateTriggers: { getFillColor: [variable, quiebres] },
        }),
      );
    }

    if (encendida('rios') && coleccion('rivers.geojson')) {
      lista.push(
        new GeoJsonLayer({
          id: 'rios',
          data: coleccion('rivers.geojson') as never,
          getLineColor: [70, 120, 175, 150],
          lineWidthMinPixels: 0.6,
        }),
      );
    }
    if (encendida('rutas') && coleccion('roads.geojson')) {
      lista.push(
        new GeoJsonLayer({
          id: 'rutas',
          data: coleccion('roads.geojson') as never,
          getLineColor: (f: ConPropiedades) =>
            (f.properties.jerarquia === 'nacional'
              ? [180, 195, 225, 190]
              : [110, 128, 168, 130]) as [number, number, number, number],
          getLineWidth: (f: ConPropiedades) => (f.properties.jerarquia === 'nacional' ? 2.2 : 1.1),
          lineWidthUnits: 'pixels',
          lineWidthMinPixels: 0.8,
          pickable: true,
          onHover: (info) => setSeñalado(info.object ? info : null),
        }),
      );
    }
    if (encendida('ferrocarril') && coleccion('rail.geojson')) {
      lista.push(
        new GeoJsonLayer({
          id: 'ferrocarril',
          data: coleccion('rail.geojson') as never,
          getLineColor: [150, 190, 220, 170],
          getDashArray: [6, 3],
          lineWidthMinPixels: 1.2,
        }),
      );
    }
    if (encendida('ductos') && coleccion('pipelines.geojson')) {
      lista.push(
        new GeoJsonLayer({
          id: 'ductos',
          data: coleccion('pipelines.geojson') as never,
          getLineColor: (f: ConPropiedades) =>
            (f.properties.tipo === 'GASODUCTO'
              ? [117, 170, 219, 150]
              : [240, 168, 48, 165]) as [number, number, number, number],
          lineWidthMinPixels: 0.7,
          pickable: true,
          onHover: (info) => setSeñalado(info.object ? info : null),
        }),
      );
    }
    if (encendida('gasoductos') && coleccion('gas_pipelines.geojson')) {
      lista.push(
        new GeoJsonLayer({
          id: 'gasoductos',
          data: coleccion('gas_pipelines.geojson') as never,
          getLineColor: [117, 170, 219, 220],
          lineWidthMinPixels: 2,
          pickable: true,
          onHover: (info) => setSeñalado(info.object ? info : null),
        }),
      );
    }

    if (encendida('pozos') && pozos.length) {
      lista.push(
        new ScatterplotLayer<Feature>({
          id: 'pozos',
          data: pozos,
          getPosition: (f) => f.geometry.coordinates as [number, number],
          // El radio va por la raíz de la acumulada: si fuera lineal, tres pozos
          // gigantes taparían la cuenca entera.
          getRadius: (f) =>
            260 + Math.sqrt(Math.max((f.properties.boe_acum_mboe as number) ?? 0, 0)) * 48,
          getFillColor: (f) => colorPozo(f.properties, pintado),
          radiusMinPixels: 1.4,
          radiusMaxPixels: 20,
          opacity: 0.9,
          pickable: true,
          onHover: (info) => setSeñalado(info.object ? info : null),
          updateTriggers: { getFillColor: [pintado] },
        }),
      );
    }

    const puntos = [
      ['instalaciones', 'facilities.geojson', PALETA.azulClaro, 2.5],
      ['terminales', 'terminals.geojson', PALETA.alza, 5],
      ['refinerias', 'refineries.geojson', PALETA.baja, 6.5],
    ] as const;
    for (const [id, archivo, color, radio] of puntos) {
      if (!encendida(id) || !coleccion(archivo)) continue;
      lista.push(
        new ScatterplotLayer<Feature>({
          id,
          data: coleccion(archivo).features,
          getPosition: (f) => f.geometry.coordinates as [number, number],
          getRadius: radio,
          radiusUnits: 'pixels',
          getFillColor: [...color, 235] as [number, number, number, number],
          stroked: true,
          getLineColor: [8, 18, 44, 220],
          lineWidthMinPixels: 1,
          pickable: true,
          onHover: (info) => setSeñalado(info.object ? info : null),
        }),
      );
    }

    if (encendida('pueblos') && coleccion('towns.geojson')) {
      const localidades = coleccion('towns.geojson').features;
      lista.push(
        new ScatterplotLayer<Feature>({
          id: 'pueblos-punto',
          data: localidades,
          getPosition: (f) => (f.geometry.coordinates as number[][])[0] as [number, number],
          getRadius: 2.5,
          radiusUnits: 'pixels',
          getFillColor: [238, 243, 255, 220],
          pickable: true,
          onHover: (info) => setSeñalado(info.object ? info : null),
        }),
        new TextLayer<Feature>({
          id: 'pueblos-texto',
          data: localidades,
          getPosition: (f) => (f.geometry.coordinates as number[][])[0] as [number, number],
          getText: (f) => (f.properties.nombre as string) ?? '',
          getSize: 11,
          getColor: [200, 214, 240, 210],
          getPixelOffset: [0, -10],
          fontFamily: 'var(--font-mono), monospace',
          outlineWidth: 3,
          outlineColor: [0, 13, 45, 220],
          fontSettings: { sdf: true },
          // Con la cuenca entera a la vista, 130 nombres se pisan entre sí.
          visible: true,
          sizeMinPixels: 9,
          sizeMaxPixels: 13,
        }),
      );
    }

    return lista;
  }, [activas, datos, raster, pozos, pintado, pintarPoligono, variable, quiebres]);

  // --- interfaz -------------------------------------------------------------
  const grupos = ['Base', 'Actividad', 'Logística', 'Territorio'] as const;
  const pesoActivo = CAPAS.filter((c) => activas.has(c.id)).reduce((suma, c) => suma + (c.peso ?? 0), 0);

  if (error) {
    return (
      <div className="rounded-lg border border-borde bg-superficie p-6 text-sm text-texto-suave">
        No se pudieron cargar las capas del mapa ({error}). Correr{' '}
        <code className="text-azul-claro">python pipeline/run_all.py</code> y{' '}
        <code className="text-azul-claro">npm run sync-data</code>.
      </div>
    );
  }

  return (
    <div className="marquesina overflow-hidden rounded-lg border border-borde bg-superficie" data-activa="true">
      <div className="grid lg:grid-cols-[17rem_1fr]">
        {/* Panel de control */}
        <div className="border-b border-borde lg:border-b-0 lg:border-r">
          <div className="max-h-[620px] space-y-5 overflow-y-auto p-4">
            <div>
              <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-tenue">
                Pintar áreas por
              </p>
              <select
                value={variable}
                onChange={(e) => setVariable(e.target.value as IdVariable)}
                className="mt-2 w-full rounded-md border border-borde bg-fondo px-2.5 py-1.5 text-sm text-texto"
              >
                {VARIABLES.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.etiqueta}
                  </option>
                ))}
              </select>
              <p className="mt-1.5 text-xs leading-snug text-texto-tenue">{definicionVariable.ayuda}</p>
            </div>

            <div>
              <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-tenue">
                Pintar pozos por
              </p>
              <div className="mt-2 flex rounded-md border border-borde p-0.5">
                {PINTADOS.map((modo) => (
                  <button
                    key={modo.id}
                    type="button"
                    onClick={() => setPintado(modo.id)}
                    className={`flex-1 rounded px-2 py-1 text-xs transition ${
                      pintado === modo.id
                        ? 'bg-superficie-alta text-azul-claro'
                        : 'text-texto-tenue hover:text-texto-suave'
                    }`}
                  >
                    {modo.etiqueta}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2.5">
              <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-tenue">
                Filtros
              </p>
              <select
                value={operador}
                onChange={(e) => setOperador(e.target.value)}
                className="w-full rounded-md border border-borde bg-fondo px-2.5 py-1.5 text-sm text-texto"
              >
                <option value="todos">Todos los operadores</option>
                {operadores.map(([nombre, cuenta]) => (
                  <option key={nombre} value={nombre}>
                    {nombre} ({cuenta})
                  </option>
                ))}
              </select>

              <label className="flex items-center gap-2 text-xs text-texto-suave">
                <input
                  type="checkbox"
                  checked={soloVacaMuerta}
                  onChange={(e) => setSoloVacaMuerta(e.target.checked)}
                  className="accent-[#0054eb]"
                />
                Solo Vaca Muerta
              </label>

              <div>
                <div className="flex items-baseline justify-between text-xs text-texto-suave">
                  <span>Desde</span>
                  <span className="tabular text-azul-claro">{desdeAnio}</span>
                </div>
                <input
                  type="range"
                  min={2006}
                  max={2026}
                  step={1}
                  value={desdeAnio}
                  onChange={(e) => setDesdeAnio(Number(e.target.value))}
                  className="mt-1 w-full accent-[#0054eb]"
                  aria-label="Año de primera producción desde"
                />
              </div>
            </div>

            {grupos.map((grupo) => (
              <div key={grupo}>
                <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-tenue">
                  {grupo}
                </p>
                <div className="mt-2 space-y-1.5">
                  {CAPAS.filter((c) => c.grupo === grupo).map((capa) => {
                    const encendida = activas.has(capa.id);
                    const bajando = capa.archivo ? cargando.has(capa.archivo) : false;
                    return (
                      <label
                        key={capa.id}
                        title={capa.ayuda}
                        className="flex cursor-pointer items-center gap-2 text-xs text-texto-suave hover:text-texto"
                      >
                        <input
                          type="checkbox"
                          checked={encendida}
                          onChange={() => alternar(capa.id)}
                          className="accent-[#0054eb]"
                        />
                        <span
                          className="h-2 w-2 shrink-0 rounded-[2px]"
                          style={{ background: `rgb(${capa.color.join(',')})` }}
                          aria-hidden="true"
                        />
                        <span className="flex-1">{capa.etiqueta}</span>
                        {bajando ? (
                          <span className="font-mono text-[0.65rem] text-oro">···</span>
                        ) : capa.peso ? (
                          <span className="font-mono text-[0.65rem] text-texto-tenue">
                            {capa.peso > 999 ? `${(capa.peso / 1024).toFixed(1)}M` : `${capa.peso}k`}
                          </span>
                        ) : null}
                      </label>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Mapa */}
        <div className="relative h-[620px] w-full">
          <DeckGL
            initialViewState={VISTA_INICIAL}
            controller
            layers={capas}
            style={{ position: 'absolute', inset: '0' }}
          />

          <div className="pointer-events-none absolute left-4 top-4 rounded-md border border-borde bg-fondo/85 px-3 py-2 backdrop-blur-sm">
            <p className="tabular text-xs text-texto-suave">
              {activas.has('pozos')
                ? `${fmt.entero(pozos.length)} de ${fmt.entero(pozosCrudos.length)} pozos`
                : 'pozos apagados'}
            </p>
            <p className="font-mono text-[0.65rem] text-texto-tenue">
              {pesoActivo > 0 ? `${(pesoActivo / 1024).toFixed(1)} MB de capas` : 'sin capas'}
            </p>
          </div>

          {archivoPoligonos && quiebres.length ? (
            <div className="pointer-events-none absolute bottom-4 left-4 rounded-md border border-borde bg-fondo/85 px-3 py-2 backdrop-blur-sm">
              <p className="font-mono text-[0.65rem] uppercase tracking-wider text-texto-tenue">
                {definicionVariable.etiqueta} ({definicionVariable.unidad})
              </p>
              <div className="mt-1.5 flex items-center gap-1">
                {[...quiebres, Infinity].map((corte, indice) => (
                  <div key={indice} className="flex flex-col items-center">
                    <span
                      className="h-2.5 w-9"
                      style={{
                        background: `rgb(${colorEscala(
                          indice === 0 ? quiebres[0] - 1 : corte === Infinity ? quiebres[quiebres.length - 1] + 1 : corte,
                          quiebres,
                          Boolean(definicionVariable.divergente),
                        ).join(',')})`,
                      }}
                    />
                    <span className="tabular mt-0.5 text-[0.6rem] text-texto-tenue">
                      {corte === Infinity ? '+' : fmt.entero(corte)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {señalado?.object ? (
            <div
              className="pointer-events-none absolute z-10 w-64 rounded-lg border border-borde-vivo bg-fondo/95 p-3 text-xs shadow-2xl"
              style={{ left: Math.min(señalado.x ?? 0, 320) + 12, top: (señalado.y ?? 0) + 12 }}
            >
              <Detalle objeto={señalado.object as Feature} capa={señalado.layer?.id ?? ''} />
            </div>
          ) : null}
        </div>
      </div>

      <p className="border-t border-borde px-4 py-3 text-xs leading-relaxed text-texto-tenue">
        Relieve: {raster?.fuente ?? 'Copernicus DEM GLO-30'}. Concesiones, pozos, ductos, refinerías e
        instalaciones: Secretaría de Energía. Rutas, localidades, ríos y ferrocarril: IGN. El NPV es
        el del pozo evaluado como si se perforara hoy, así que un pozo viejo con NPV negativo no dio
        pérdida: no repagaría el capex de hoy.
      </p>
    </div>
  );
}

/** Qué mostrar de cada cosa que se puede señalar. Cada capa tiene su ficha
 *  porque una concesión y un ducto no se describen con los mismos campos. */
function Detalle({ objeto, capa }: { objeto: Feature; capa: string }) {
  const p = objeto.properties;
  const fila = (etiqueta: string, valor: React.ReactNode) => (
    <div className="flex justify-between gap-3">
      <dt className="text-texto-tenue">{etiqueta}</dt>
      <dd className="tabular text-right">{valor}</dd>
    </div>
  );

  if (capa === 'concesiones' || capa === 'yacimientos') {
    const npv = p.npv_musd_mediano as number | null;
    return (
      <>
        <p className="font-medium text-texto">{(p.nombre ?? p.yacimiento) as string}</p>
        <p className="mt-0.5 text-texto-tenue">{(p.operador_principal ?? p.operador) as string}</p>
        <dl className="mt-2 space-y-1 text-texto-suave">
          {fila('Pozos', fmt.entero(p.pozos as number))}
          {fila('Acumulada', `${fmt.entero(p.boe_acum_mboe as number)} Mboe`)}
          {fila('Por pozo', `${fmt.entero(p.boe_por_pozo_mboe as number)} Mboe`)}
          {npv !== null && npv !== undefined
            ? fila(
                'NPV mediano',
                <span className={npv >= 0 ? 'text-alza' : 'text-baja'}>US$ {fmt.numero(npv, 1)}M</span>,
              )
            : null}
        </dl>
      </>
    );
  }

  if (capa === 'pozos') {
    const npv = p.npv_musd as number | null;
    return (
      <>
        <p className="font-medium text-texto">{p.sigla as string}</p>
        <p className="mt-0.5 text-texto-tenue">
          {p.operador as string} · {p.yacimiento as string}
        </p>
        <dl className="mt-2 space-y-1 text-texto-suave">
          {fila('Acumulada', `${fmt.numero(p.boe_acum_mboe as number, 1)} Mboe`)}
          {p.eur_mbbl ? fila('EUR', `${fmt.numero(p.eur_mbbl as number, 1)} Mbbl`) : null}
          {npv !== null && npv !== undefined
            ? fila(
                'NPV',
                <span className={npv >= 0 ? 'text-alza' : 'text-baja'}>US$ {fmt.numero(npv, 1)}M</span>,
              )
            : null}
          {p.anio_inicio ? fila('Primera producción', p.anio_inicio as number) : null}
        </dl>
      </>
    );
  }

  const titulo =
    (p.nombre as string) ?? (p.empresa as string) ?? (p.ruta as string) ?? 'Sin nombre';
  const detalles = ['empresa', 'tipo', 'descripcion', 'jerarquia', 'localidad', 'provincia'].filter(
    (clave) => p[clave] && p[clave] !== titulo,
  );
  return (
    <>
      <p className="font-medium text-texto">{titulo}</p>
      <dl className="mt-2 space-y-1 text-texto-suave">
        {detalles.map((clave) => fila(clave[0].toUpperCase() + clave.slice(1), String(p[clave])))}
      </dl>
    </>
  );
}
