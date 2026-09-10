// Un gráfico hecho de barriles.
//
// Es una idea vieja —el pictograma de Otto Neurath, el de "un muñequito por
// cada mil obreros"— aplicada a lo que este proyecto cuenta. Diez barriles
// valen el total y se llenan de a uno: el lector no lee un porcentaje, ve
// cuántos barriles de cada diez.
//
// Sirve donde la proporción es el dato y no un detalle: cuánto de lo que
// produce Upstream se lo vende a la propia YPF, cuánto del capex se va a un
// solo negocio, cuánto de la producción es shale. En una tabla eso es un
// número más; acá es la primera cosa que se ve.

import { Barril } from '@/components/ilustraciones/piezas';

export function MedidorBarriles({
  proporcion,
  cantidad = 10,
  etiqueta,
  detalle,
  className,
}: {
  /** De 0 a 1. */
  proporcion: number;
  cantidad?: number;
  etiqueta: string;
  detalle?: string;
  className?: string;
}) {
  const valor = Math.max(0, Math.min(1, proporcion));
  const llenos = valor * cantidad;
  const ancho = cantidad * 26 + 8;

  return (
    <div className={className}>
      <svg
        viewBox={`0 0 ${ancho} 46`}
        className="w-full"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
        role="img"
        aria-label={`${etiqueta}: ${(valor * 100).toFixed(0)} de cada 100`}
      >
        {Array.from({ length: cantidad }).map((_, indice) => {
          // Cada barril se llena entero antes de que empiece el siguiente, y el
          // último queda a medias: ahí está la fracción que no llega a barril.
          const llenado = Math.max(0, Math.min(1, llenos - indice));
          return (
            <Barril
              key={indice}
              x={17 + indice * 26}
              y={42}
              escala={0.62}
              llenado={llenado}
              opacidad={llenado > 0 ? 1 : 0.45}
              brillo={false}
            />
          );
        })}
      </svg>
      <p className="mt-1 text-[0.7rem] leading-snug text-texto-tenue">
        <span className="text-oro">{(valor * 100).toFixed(0)} de cada 100</span> · {etiqueta}
        {detalle ? <span className="block text-texto-tenue/80">{detalle}</span> : null}
      </p>
    </div>
  );
}
