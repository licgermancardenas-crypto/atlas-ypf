// Qué es cada negocio y de qué color se dibuja.
//
// Vive fuera del componente porque lo usan los dos lados: el módulo interactivo
// y la página, que arma la grilla de negocios en el servidor. Los datos duros
// —capacidad de refinación, cantidad de estaciones— salen del 20-F, no de la
// memoria: si cambian, cambian ahí primero.

export const COLOR: Record<string, string> = {
  Upstream: 'var(--color-azul)',
  'Midstream y Downstream': 'var(--color-oro)',
  Downstream: 'var(--color-oro)',
  Industrialización: 'var(--color-oro)',
  Comercialización: 'var(--color-celeste)',
  'Gas y energía': 'var(--color-alza)',
  'GNL y gas integrado': 'var(--color-alza)',
  'Nuevas energías': 'var(--color-celeste)',
  'Administración central y otros': 'var(--color-neutro)',
  'Ajustes de consolidación': 'var(--color-baja)',
};

export const QUE_HACE: Record<string, { titulo: string; texto: string; datos: string[] }> = {
  Upstream: {
    titulo: 'Sacar el petróleo y el gas de la roca',
    texto:
      'Exploración y producción. Es el negocio donde está Vaca Muerta y donde se juega la tesis del caso: un pozo horizontal con fractura hidráulica produce mucho al principio y declina rápido, así que crecer exige perforar todos los años. Por eso se lleva la mayor parte del capex.',
    datos: ['Se lleva el grueso de la inversión', 'Casi no le vende al mercado: le vende a la propia YPF'],
  },
  'Midstream y Downstream': {
    titulo: 'Refinar, transportar y vender',
    texto:
      'Toma el crudo —propio y de terceros—, lo convierte en nafta y gasoil y lo vende en la red de estaciones. Es la cara de la compañía frente al mercado y la que cobra casi toda la facturación externa. Su margen depende de la diferencia entre lo que paga por el crudo y lo que puede cobrar en el surtidor, que en la Argentina no siempre es una decisión de la empresa.',
    datos: [
      'Tres refinerías propias: La Plata, Luján de Cuyo y Plaza Huincul',
      'Capacidad de refinación agregada de 123,4 Mbbl por día',
      'Alrededor de 1.600 estaciones de servicio',
    ],
  },
  'GNL y gas integrado': {
    titulo: 'El gas, de la cuenca al barco',
    texto:
      'Reúne el negocio de gas integrado y el proyecto de exportación de GNL. Factura poco en relación con su capex y su resultado operativo suele estar cerca de cero o en rojo: es un negocio en construcción, no uno maduro, y su valor está en lo que puede llegar a ser.',
    datos: ['El proyecto Argentina LNG se desarrolla con socios, en operaciones conjuntas'],
  },
  'Nuevas energías': {
    titulo: 'Electricidad y renovables',
    texto:
      'Generación eléctrica y energías renovables, el negocio de YPF Luz. Es chico dentro del consolidado, tiene márgenes distintos a los del petróleo y su activo es una central, no un yacimiento: dura décadas y no declina.',
    datos: ['Incluye YPF Luz y su subsidiaria Central Dock Sud'],
  },
  'Administración central y otros': {
    titulo: 'Lo que no es un negocio',
    texto:
      'La estructura corporativa y las actividades que no se asignan a ningún segmento. Su resultado operativo es negativo por definición: son costos que la compañía tiene y que ningún negocio reclama como propios.',
    datos: [],
  },
  'Ajustes de consolidación': {
    titulo: 'Descontar lo que la compañía se vende a sí misma',
    texto:
      'No es un negocio: es la resta. Cuando Upstream le vende crudo a Downstream, esa venta figura en los dos lados y hay que eliminarla para que el total no cuente dos veces el mismo barril. Su tamaño es exactamente la medida de cuán integrada está la compañía.',
    datos: [],
  },
};
