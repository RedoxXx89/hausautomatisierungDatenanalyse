import dataclasses
import mysql.connector
import matplotlib.pyplot as plt
from mysqlSecrets import MySQLSecrets

secrets = MySQLSecrets()

@dataclasses.dataclass
class AbgasTemperatur:
    time: int          # Unix Timestamp
    temperatur: float
    temperaturGradient: float = 0.0
    brennerStatus: bool | None = None

AbgasTemperaturDaten: list[AbgasTemperatur] = []

def brennerStatusAnalyse():
    global AbgasTemperaturDaten

    leseAbgasTemperatur()

    for index, abgas in enumerate(AbgasTemperaturDaten):
        startTemperatur = abgas.temperatur
        startZeitstempel = abgas.time
        stopTemperatur = AbgasTemperaturDaten[index + 1].temperatur if index + 1 < len(AbgasTemperaturDaten) else None
        stopZeitstempel = AbgasTemperaturDaten[index + 1].time if index + 1 < len(AbgasTemperaturDaten) else None

        if stopTemperatur is not None:
            temperaturDifferenz = stopTemperatur - startTemperatur
            zeitDifferenz = stopZeitstempel - startZeitstempel
            temperaturGradient = temperaturDifferenz / zeitDifferenz if zeitDifferenz != 0 else 0
            abgas.temperaturGradient = temperaturGradient
            AbgasTemperaturDaten[index].temperaturGradient = temperaturGradient

            print(f"Temperaturgradient: {AbgasTemperaturDaten[index].temperaturGradient}°C/Sekunde")

            if abgas.temperaturGradient > 0.5:
                abgas.brennerStatus = True
                print("Brennerstatus: An")
            elif abgas.temperaturGradient < -0.5:
                abgas.brennerStatus = False
                print("Brennerstatus: Aus")

    plotBrennerStatus()
        
def plotBrennerStatus():
    global AbgasTemperaturDaten

    times = [abgas.time for abgas in AbgasTemperaturDaten]
    gradients = [abgas.temperaturGradient for abgas in AbgasTemperaturDaten]
    temperatur = [abgas.temperatur for abgas in AbgasTemperaturDaten]
    statuses = [abgas.brennerStatus for abgas in AbgasTemperaturDaten]

    fig, ax1 = plt.subplots(figsize=(12, 6))

    ax1.plot(times, gradients, label='Temperaturgradient (°C/Sekunde)', color='blue')
    ax1.plot(times, temperatur, label='Temperatur (°C)', color='green')
    ax1.set_xlabel('Zeit (Unix Timestamp)')
    ax1.set_ylabel('Temperatur / Gradient')
    ax1.grid()

    ax2 = ax1.twinx()
    ax2.scatter(times, statuses, label='Brennerstatus (1=An, 0=Aus)', color='red', marker='x')
    ax2.set_ylabel('Brennerstatus (0=Aus, 1=An)')
    ax2.set_ylim(-0.5, 1.5)
    ax2.set_yticks([0, 1])

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2)

    plt.title('Brennerstatus Analyse basierend auf Temperaturgradienten')
    plt.show()


def leseAbgasTemperatur():
    global AbgasTemperaturDaten
    AbgasTemperaturDaten.clear()

    conn = mysql.connector.connect(
        host=secrets.host,
        user=secrets.user,
        password=secrets.password,
        database=secrets.database_oelheizung
    )

    cursor = conn.cursor()

    cursor.execute("""
        SELECT UNIX_TIMESTAMP(time), temperatur
        FROM oelheizung.abgastemperatur
        WHERE time >= NOW() - INTERVAL 12 HOUR
        ORDER BY time ASC
    """)

    rows = cursor.fetchall()

    for ts, temperatur in rows:
        AbgasTemperaturDaten.append(AbgasTemperatur(time=ts, temperatur=temperatur))

    cursor.close()
    conn.close()


if __name__ == "__main__":
    brennerStatusAnalyse()
