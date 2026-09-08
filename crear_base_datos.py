# -*- coding: utf-8 -*-
"""
crear_base_datos.py — Crea (o recrea) refugio.db con el catálogo de mascotas,
incluyendo una foto de banco gratuito por cada una.

Corre esto UNA VEZ (o cada vez que quieras resetear el catálogo a los datos base):
    python crear_base_datos.py
"""

import sqlite3

RUTA_DB = "refugio.db"

# Fotos de bancos gratuitos pensados para placeholders (sin derechos de autor,
# libres de usar en proyectos): place.dog para perros, placekitten.com para gatos.
# El "id" fija siempre la misma foto para esa mascota.
mascotas_data = [
    dict(id="M001", nombre="Rocky", especie="Perro", raza="Mestizo (tamaño grande)", edad="3 años", tamano="Grande",
         sexo="Macho", esterilizado="Sí", vacunado="Sí",
         temperamento="Juguetón, muy sociable con otros perros, un poco tímido con desconocidos al inicio",
         descripcion="Rocky llegó al refugio hace 8 meses tras ser rescatado de la calle. Le encanta correr en espacios abiertos y aprendió a sentarse y dar la pata. Ideal para una casa con patio.",
         requisitos="Casa con patio o acceso a paseos largos diarios. Visita domiciliaria previa.",
         cuota_adopcion="$800 (incluye esterilización y cartilla de vacunación)",
         refugio="Refugio Huellas Felices", urgente="",
         foto_url="https://place.dog/500/500?id=101"),
    dict(id="M002", nombre="Mia", especie="Gato", raza="Mestiza pelo corto", edad="1 año", tamano="Chico",
         sexo="Hembra", esterilizado="Sí", vacunado="Sí",
         temperamento="Independiente, cariñosa a su ritmo, le gusta observar desde las alturas",
         descripcion="Mia fue encontrada como cría junto a sus hermanos. Es curiosa y juguetona con plumeros y pelotas. Se lleva bien con otros gatos tranquilos.",
         requisitos="Departamento o casa con mallas de protección en ventanas/balcones.",
         cuota_adopcion="$600 (incluye esterilización y cartilla de vacunación)",
         refugio="Refugio Huellas Felices", urgente="",
         foto_url="https://loremflickr.com/500/500/cat?lock=1"),
    dict(id="M003", nombre="Tango", especie="Perro", raza="Labrador mestizo", edad="7 años", tamano="Grande",
         sexo="Macho", esterilizado="Sí", vacunado="Sí",
         temperamento="Tranquilo, cariñoso, ya no tiene tanta energía pero ama las caricias",
         descripcion="Tango es un perro senior que fue entregado al refugio porque sus dueños se mudaron de país. Le urge un hogar tranquilo porque los perros mayores tardan mucho más en ser adoptados.",
         requisitos="Familia sin niños muy pequeños, casa tranquila, disposición a cuidados de perro senior (chequeos veterinarios cada 6 meses).",
         cuota_adopcion="$400 (cuota reducida por ser adopción prioritaria de mascota senior)",
         refugio="Refugio Segunda Oportunidad", urgente="URGENTE: mascota senior con adopción prioritaria, cuota reducida",
         foto_url="https://place.dog/500/500?id=102"),
    dict(id="M004", nombre="Luna", especie="Gato", raza="Mestiza pelo largo", edad="4 años", tamano="Mediano",
         sexo="Hembra", esterilizado="Sí", vacunado="Sí",
         temperamento="Cariñosa, tranquila, le gusta dormir en regazos",
         descripcion="Luna tiene FIV positivo (inmunodeficiencia felina) pero puede vivir una vida normal y larga si es la única gata de la casa o convive con gatos también FIV+.",
         requisitos="Hogar sin otros gatos FIV negativo, o como gata única. Chequeos veterinarios cada 6 meses.",
         cuota_adopcion="$300 (cuota reducida, incluye esterilización y cartilla)",
         refugio="Refugio Segunda Oportunidad", urgente="URGENTE: requiere hogar con experiencia en cuidados especiales",
         foto_url="https://loremflickr.com/500/500/cat?lock=2"),
    dict(id="M005", nombre="Toby", especie="Perro", raza="Beagle", edad="2 años", tamano="Mediano",
         sexo="Macho", esterilizado="Sí", vacunado="Sí",
         temperamento="Muy activo, curioso, le encanta olfatear todo, un poco terco para obedecer",
         descripcion="Toby es un beagle con mucha energía. Necesita paseos largos y estimulación mental (juguetes de olfato) o puede volverse destructivo por aburrimiento.",
         requisitos="Familia activa, mínimo 1 hora de paseo diario, experiencia previa con perros es un plus.",
         cuota_adopcion="$800 (incluye esterilización y cartilla de vacunación)",
         refugio="Refugio Huellas Felices", urgente="",
         foto_url="https://place.dog/500/500?id=103"),
    dict(id="M006", nombre="Nube", especie="Gato", raza="Mestiza blanca", edad="6 meses", tamano="Chico",
         sexo="Hembra", esterilizado="No (se esteriliza al cumplir la edad mínima)", vacunado="Primera dosis aplicada",
         temperamento="Juguetona, hiperactiva típica de cachorra, muy sociable",
         descripcion="Nube es una gatita cachorra rescatada junto a su camada. Se recomienda adoptarla junto a otro gatito para que gaste energía jugando.",
         requisitos="Compromiso de esterilizarla a los 6 meses (el refugio cubre el costo). Ideal adoptar en pareja.",
         cuota_adopcion="$450 (incluye esterilización programada y vacunas)",
         refugio="Refugio Patitas al Rescate", urgente="",
         foto_url="https://loremflickr.com/500/500/cat?lock=3"),
    dict(id="M007", nombre="Bruno", especie="Perro", raza="Pastor Alemán mestizo", edad="5 años", tamano="Grande",
         sexo="Macho", esterilizado="Sí", vacunado="Sí",
         temperamento="Leal, protector, necesita reglas claras y un dueño con experiencia en manejo canino",
         descripcion="Bruno fue devuelto dos veces al refugio por no tener suficiente ejercicio en sus hogares anteriores. Es un perro noble pero necesita estructura y actividad física constante.",
         requisitos="Experiencia previa con razas grandes/dominantes. Casa con patio grande y cercado.",
         cuota_adopcion="$700 (incluye esterilización y cartilla de vacunación)",
         refugio="Refugio Patitas al Rescate", urgente="URGENTE: tercera vez en el refugio, riesgo de estrés crónico si no encuentra hogar definitivo",
         foto_url="https://place.dog/500/500?id=104"),
    dict(id="M008", nombre="Coco", especie="Gato", raza="Mestizo naranja", edad="2 años", tamano="Mediano",
         sexo="Macho", esterilizado="Sí", vacunado="Sí",
         temperamento="Sociable, ronronea con todo el mundo, le encanta la comida",
         descripcion="Coco es de los gatos más queridos del refugio por lo cariñoso que es con todos, incluidos niños y otras mascotas.",
         requisitos="Sin requisitos especiales, apto para familias con niños.",
         cuota_adopcion="$600 (incluye esterilización y cartilla de vacunación)",
         refugio="Refugio Huellas Felices", urgente="",
         foto_url="https://loremflickr.com/500/500/cat?lock=4"),
    dict(id="M009", nombre="Maple", especie="Perro", raza="Chihuahua mestizo", edad="9 años", tamano="Chico",
         sexo="Hembra", esterilizado="Sí", vacunado="Sí",
         temperamento="Tranquila, apegada a una sola persona, algo desconfiada con extraños",
         descripcion="Maple es una perrita senior con un soplo cardiaco leve controlado con medicamento diario. Necesita un hogar tranquilo y paciente.",
         requisitos="Compromiso de administrar medicamento diario y chequeos veterinarios cada 3 meses.",
         cuota_adopcion="$250 (cuota reducida, mascota senior con cuidados especiales)",
         refugio="Refugio Segunda Oportunidad", urgente="URGENTE: mascota senior con cuidados médicos, adopción prioritaria",
         foto_url="https://place.dog/500/500?id=105"),
    dict(id="M010", nombre="Simba", especie="Gato", raza="Mestizo atigrado", edad="3 años", tamano="Mediano",
         sexo="Macho", esterilizado="Sí", vacunado="Sí",
         temperamento="Curioso, activo, le encanta trepar y jugar con cuerdas",
         descripcion="Simba llegó por abandono cuando su familia se mudó. Se adapta rápido a hogares nuevos y convive bien con perros tranquilos.",
         requisitos="Espacio vertical para trepar (rascadores/repisas) recomendado.",
         cuota_adopcion="$600 (incluye esterilización y cartilla de vacunación)",
         refugio="Refugio Patitas al Rescate", urgente="",
         foto_url="https://loremflickr.com/500/500/cat?lock=5"),
]

CAMPOS = ["id", "nombre", "especie", "raza", "edad", "tamano", "sexo", "esterilizado",
          "vacunado", "temperamento", "descripcion", "requisitos", "cuota_adopcion",
          "refugio", "urgente", "foto_url"]


def crear_base_datos():
    conexion = sqlite3.connect(RUTA_DB)
    cursor = conexion.cursor()

    cursor.execute("DROP TABLE IF EXISTS mascotas")
    cursor.execute("""
        CREATE TABLE mascotas (
            id TEXT PRIMARY KEY,
            nombre TEXT,
            especie TEXT,
            raza TEXT,
            edad TEXT,
            tamano TEXT,
            sexo TEXT,
            esterilizado TEXT,
            vacunado TEXT,
            temperamento TEXT,
            descripcion TEXT,
            requisitos TEXT,
            cuota_adopcion TEXT,
            refugio TEXT,
            urgente TEXT,
            foto_url TEXT
        )
    """)

    placeholders = ", ".join(["?"] * len(CAMPOS))
    filas = [tuple(m[campo] for campo in CAMPOS) for m in mascotas_data]
    cursor.executemany(f"INSERT INTO mascotas VALUES ({placeholders})", filas)

    conexion.commit()
    conexion.close()
    print(f"Base de datos '{RUTA_DB}' creada con {len(mascotas_data)} mascotas ✅")


if __name__ == "__main__":
    crear_base_datos()
