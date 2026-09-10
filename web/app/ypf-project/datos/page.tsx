import { Panel } from '@/components/Panel';
import { Shell } from '@/components/Shell';
import { Dato, Franja, Tabla } from '@/components/ui';
import { fmt, type Financieros } from '@/lib/data';
import { cargar } from '@/lib/server-data';

// El módulo de datos: la máquina, a la vista.
//
// Un caso que muestra conclusiones y esconde de dónde salieron pide un acto de
// fe. Acá está la lista completa: cada fuente con su URL, cuántas filas trajo,
// cuándo se bajó, qué transform la consume y qué chequeos tiene que pasar antes
// de que el dato se publique. Es la parte del trabajo que normalmente no se ve
// y la que distingue un pipeline de un Excel bajado a mano.

export const metadata = {
  title: 'Datos — ATLAS-YPF',
  description:
    'Catálogo de fuentes, datasets crudos, salidas procesadas, etapas del pipeline y chequeos de calidad.',
};

interface Catalogo {
  generado: string;
  resumen: {
    datasets_crudos: number;
    salidas_procesadas: number;
    fuentes: number;
    bytes_crudos: number;
    bytes_procesados: number;
    filas_crudas: number;
  };
  fuentes: { fuente: string; organismo: string; por_que: string; datasets: number; filas: number; bytes: number }[];
  crudos: {
    clave: string;
    fuente: string;
    detalle: string | null;
    filas: number | null;
    bytes: number | null;
    descargado: string;
    url: string | null;
    ruta: string | null;
    sha256: string | null;
    nota: string | null;
  }[];
  procesados: {
    clave: string;
    generado: string;
    salidas: string[];
    bytes: number;
    metricas: Record<string, string | number | boolean | null>;
  }[];
  etapas: { tipo: string; nombre: string; script: string }[];
  chequeos: { nombre: string; descripcion: string }[];
}

function peso(bytes: number | null): string {
  if (!bytes) return '—';
  if (bytes >= 1024 ** 3) return `${fmt.numero(bytes / 1024 ** 3, 2)} GB`;
  if (bytes >= 1024 ** 2) return `${fmt.numero(bytes / 1024 ** 2, 1)} MB`;
  return `${fmt.numero(bytes / 1024, 0)} KB`;
}

export default async function ModuloDatos() {
  const [catalogo, financieros] = await Promise.all([
    cargar<Catalogo>('catalogo.json'),
    cargar<Financieros>('financials_ypf.json'),
  ]);

  const ingestas = catalogo.etapas.filter((etapa) => etapa.tipo === 'ingesta');
  const transforms = catalogo.etapas.filter((etapa) => etapa.tipo === 'transform');

  return (
    <Shell actualizado={financieros.generado.slice(0, 10)} operadores={[]} modulo="datos">
      <main className="mx-auto max-w-6xl px-6 py-12">
        <Franja className="w-24" />
        <h1 className="mt-5 text-3xl font-bold sm:text-4xl">Datos</h1>
        <p className="mt-3 max-w-3xl leading-relaxed text-texto-suave">
          Todo lo que el caso afirma sale de estas fuentes, y cada una tiene acá su URL, su fecha de
          descarga y su cantidad de filas. El pipeline se puede volver a correr entero con un
          comando y se refresca solo todos los lunes.
        </p>

        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Dato
            etiqueta="Datasets crudos"
            valor={fmt.entero(catalogo.resumen.datasets_crudos)}
            detalle={`de ${catalogo.resumen.fuentes} fuentes distintas`}
            tono="marca"
          />
          <Dato
            etiqueta="Filas ingeridas"
            valor={fmt.entero(catalogo.resumen.filas_crudas)}
            detalle={`${peso(catalogo.resumen.bytes_crudos)} de datos crudos`}
          />
          <Dato
            etiqueta="Salidas del pipeline"
            valor={fmt.entero(catalogo.resumen.salidas_procesadas)}
            detalle={`${peso(catalogo.resumen.bytes_procesados)} que consume la web`}
            tono="alza"
          />
          <Dato
            etiqueta="Etapas"
            valor={`${ingestas.length} + ${transforms.length}`}
            detalle="ingestas y transforms encadenados"
          />
          <Dato
            etiqueta="Chequeos de calidad"
            valor={fmt.entero(catalogo.chequeos.length)}
            detalle="corren al final; si fallan, no se publica"
            tono="crudo"
          />
          <Dato
            etiqueta="Última corrida"
            valor={catalogo.generado.slice(0, 10)}
            detalle="refresco automático los lunes"
          />
        </div>

        <div className="mt-8 space-y-6">
          <Panel
            titulo="Las fuentes"
            archivo="atlas-ypf-fuentes"
            etiquetaVista="Detalle"
            columnas={[
              { clave: 'fuente', titulo: 'Fuente' },
              { clave: 'datasets', titulo: 'Datasets', alineacion: 'der' },
              { clave: 'filas', titulo: 'Filas', alineacion: 'der' },
              { clave: 'bytes', titulo: 'Bytes', alineacion: 'der' },
            ]}
            datos={catalogo.fuentes as unknown as Record<string, unknown>[]}
          >
            <Tabla
              columnas={[
                { clave: 'fuente', titulo: 'Fuente' },
                { clave: 'organismo', titulo: 'Organismo' },
                { clave: 'porQue', titulo: 'Para qué entra' },
                { clave: 'datasets', titulo: 'Datasets', alineacion: 'der' },
                { clave: 'peso', titulo: 'Peso', alineacion: 'der' },
              ]}
              filas={catalogo.fuentes.map((fila) => ({
                fuente: <span className="text-texto">{fila.fuente}</span>,
                organismo: fila.organismo,
                porQue: <span className="text-texto-tenue">{fila.por_que}</span>,
                datasets: fmt.entero(fila.datasets),
                peso: peso(fila.bytes),
              }))}
            />
          </Panel>

          <Panel
            titulo={`Datasets crudos (${catalogo.crudos.length})`}
            archivo="atlas-ypf-datasets"
            etiquetaVista="Detalle"
            columnas={[
              { clave: 'clave', titulo: 'Dataset' },
              { clave: 'fuente', titulo: 'Fuente' },
              { clave: 'filas', titulo: 'Filas', alineacion: 'der' },
              { clave: 'bytes', titulo: 'Bytes', alineacion: 'der' },
              { clave: 'descargado', titulo: 'Descargado' },
              { clave: 'url', titulo: 'URL' },
            ]}
            datos={catalogo.crudos as unknown as Record<string, unknown>[]}
            nota="El hash es el de la descarga: permite verificar que el archivo del que salió una conclusión es el mismo que está hoy en disco. data/raw/ nunca se commitea; se regenera corriendo el pipeline."
          >
            <Tabla
              columnas={[
                { clave: 'clave', titulo: 'Dataset' },
                { clave: 'fuente', titulo: 'Fuente' },
                { clave: 'filas', titulo: 'Filas', alineacion: 'der' },
                { clave: 'peso', titulo: 'Peso', alineacion: 'der' },
                { clave: 'descargado', titulo: 'Descargado' },
                { clave: 'hash', titulo: 'sha256' },
              ]}
              filas={catalogo.crudos.map((fila) => ({
                clave: fila.url ? (
                  <a
                    href={fila.url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="text-azul-claro hover:underline"
                    title={fila.detalle ?? undefined}
                  >
                    {fila.clave}
                  </a>
                ) : (
                  fila.clave
                ),
                fuente: <span className="text-texto-tenue">{fila.fuente}</span>,
                filas: fila.filas ? fmt.entero(fila.filas) : '—',
                peso: peso(fila.bytes),
                descargado: <span className="text-texto-tenue">{fila.descargado.slice(0, 10)}</span>,
                hash: (
                  <span className="font-mono text-[0.65rem] text-texto-tenue" title={fila.sha256 ?? undefined}>
                    {fila.sha256 ? `${fila.sha256.slice(0, 12)}…` : '—'}
                  </span>
                ),
              }))}
            />
          </Panel>

          <Panel
            titulo="Lo que produce el pipeline"
            archivo="atlas-ypf-salidas"
            etiquetaVista="Detalle"
            columnas={[
              { clave: 'clave', titulo: 'Transform' },
              { clave: 'generado', titulo: 'Generado' },
              { clave: 'bytes', titulo: 'Bytes', alineacion: 'der' },
            ]}
            datos={catalogo.procesados as unknown as Record<string, unknown>[]}
          >
            <Tabla
              columnas={[
                { clave: 'clave', titulo: 'Transform' },
                { clave: 'salidas', titulo: 'Archivos que genera' },
                { clave: 'metricas', titulo: 'Lo que dejó registrado' },
                { clave: 'peso', titulo: 'Peso', alineacion: 'der' },
              ]}
              filas={catalogo.procesados.map((fila) => ({
                clave: <span className="text-texto">{fila.clave}</span>,
                salidas: (
                  <span className="text-texto-tenue">
                    {fila.salidas.map((salida) => salida.split('/').pop()).join(', ')}
                  </span>
                ),
                metricas: (
                  <span className="text-texto-tenue">
                    {Object.entries(fila.metricas)
                      .slice(0, 3)
                      .map(([clave, valor]) => `${clave}: ${valor}`)
                      .join(' · ') || '—'}
                  </span>
                ),
                peso: peso(fila.bytes),
              }))}
            />
          </Panel>

          <div className="grid gap-6 lg:grid-cols-2">
            <div className="marquesina rounded-lg border border-borde bg-superficie p-5">
              <h3 className="text-sm font-medium text-texto-suave">Las etapas, en orden</h3>
              <ol className="mt-4 space-y-1 text-xs">
                {catalogo.etapas.map((etapa, indice) => (
                  <li key={etapa.nombre} className="flex items-baseline gap-2">
                    <span className="tabular w-6 shrink-0 text-texto-tenue">
                      {String(indice + 1).padStart(2, '0')}
                    </span>
                    <span
                      className={
                        etapa.tipo === 'ingesta' ? 'text-celeste' : 'text-azul-claro'
                      }
                    >
                      {etapa.tipo}
                    </span>
                    <span className="text-texto-suave">{etapa.nombre}</span>
                    <span className="ml-auto font-mono text-[0.65rem] text-texto-tenue">
                      {etapa.script.split('/').pop()}
                    </span>
                  </li>
                ))}
              </ol>
              <p className="mt-4 text-xs leading-relaxed text-texto-tenue">
                Cada etapa corre como subproceso. Si una falla, el exit code se propaga y el job de
                GitHub Actions queda en rojo en vez de publicar datos a medias.
              </p>
            </div>

            <div className="marquesina rounded-lg border border-borde bg-superficie p-5">
              <h3 className="text-sm font-medium text-texto-suave">
                Los chequeos que corren antes de publicar
              </h3>
              <ul className="mt-4 space-y-1.5 text-xs">
                {catalogo.chequeos.map((chequeo) => (
                  <li key={chequeo.nombre} className="flex items-baseline gap-2">
                    <span className="text-alza" aria-hidden="true">
                      ✓
                    </span>
                    <span>
                      <span className="text-texto-suave">{chequeo.nombre}</span>
                      <span className="block leading-snug text-texto-tenue">
                        {chequeo.descripcion}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-4 text-xs leading-relaxed text-texto-tenue">
                No verifican que el dato sea correcto: verifican que no sea imposible. Que las
                partes sumen al total, que ningún operador concentre una fracción absurda del país,
                que las coordenadas caigan en la Argentina. Este proyecto ya tuvo dos errores de
                datos que llegaron hasta el final y se encontraron mirando; estos chequeos existen
                para que el tercero no dependa de la suerte.
              </p>
            </div>
          </div>
        </div>

        <p className="mt-8 text-xs leading-relaxed text-texto-tenue">
          Catálogo generado el {catalogo.generado.slice(0, 10)} a partir de los manifiestos que el
          propio pipeline escribe en cada corrida. Las etapas y los chequeos se leen del código, no
          de una lista aparte: si mañana se agrega un ingest, aparece acá sin que nadie se acuerde
          de actualizarlo.
        </p>
      </main>
    </Shell>
  );
}
