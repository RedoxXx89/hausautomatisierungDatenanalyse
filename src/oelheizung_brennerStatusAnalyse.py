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

@dataclasses.dataclass
class BrennerStatus:
    time: int          # start time of the status
    status: bool
    period: int | None = None  # duration of the status in seconds

@dataclasses.dataclass
class brennerStatistik:
    gesamtdauerAktiv: int = 0
    gesamtdauerInaktiv: int = 0
    starts: int = 0
    pausen: int = 0
    mittlereDauerAktiv: float = 0.0
    mittlereDauerInaktiv: float = 0.0



BrennerStatistikDaten: brennerStatistik = brennerStatistik()
BrennerStatusDaten: list[BrennerStatus] = []
AbgasTemperaturDaten: list[AbgasTemperatur] = []


def brennerStatusAnalyse():
    global AbgasTemperaturDaten

    leseAbgasTemperatur()
    berechneBrennerStatus()
    analysiereBrennerNutzung()
    plotBrennerStatus()


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
        WHERE time >= NOW() - INTERVAL 24 HOUR
        ORDER BY time ASC
    """)

    rows = cursor.fetchall()

    for ts, temperatur in rows:
        AbgasTemperaturDaten.append(AbgasTemperatur(time=ts, temperatur=temperatur))

    cursor.close()
    conn.close()


def berechneBrennerStatus():
    global AbgasTemperaturDaten

    # Berechnung des Brennerstatus basierend auf dem Temperaturgradienten
    for index, abgas in enumerate(AbgasTemperaturDaten):
        startTemperatur = abgas.temperatur
        startZeitstempel = abgas.time
        stopTemperatur = AbgasTemperaturDaten[index + 1].temperatur if index + 1 < len(AbgasTemperaturDaten) else None
        stopZeitstempel = AbgasTemperaturDaten[index + 1].time if index + 1 < len(AbgasTemperaturDaten) else None

        # Berechnung des Temperaturgradienten zwischen den aktuellen und nächsten Messwerten
        if stopTemperatur is not None:
            temperaturDifferenz = stopTemperatur - startTemperatur
            zeitDifferenz = stopZeitstempel - startZeitstempel
            temperaturGradient = temperaturDifferenz / zeitDifferenz if zeitDifferenz != 0 else 0
            abgas.temperaturGradient = temperaturGradient
            AbgasTemperaturDaten[index].temperaturGradient = temperaturGradient

            if abgas.temperaturGradient > 0.5:
                abgas.brennerStatus = True
            elif abgas.temperaturGradient < -0.5:
                abgas.brennerStatus = False

    # Fehlende Brennerstatus-Werte mit vorherigen Werten auffüllen
    for index, abgas in enumerate(AbgasTemperaturDaten):
        if abgas.brennerStatus is None:
            if index > 0 and AbgasTemperaturDaten[index - 1].brennerStatus is not None:
                abgas.brennerStatus = AbgasTemperaturDaten[index - 1].brennerStatus


def analysiereBrennerNutzung():
    global AbgasTemperaturDaten, BrennerStatusDaten, BrennerStatistikDaten

    BrennerStatusDaten.clear()

    aktuellerStatus = None
    startZeit = None

    for abgas in AbgasTemperaturDaten:
        if abgas.brennerStatus != aktuellerStatus:
            if aktuellerStatus is not None:
                BrennerStatusDaten.append(BrennerStatus(time=startZeit, status=aktuellerStatus, period=abgas.time - startZeit))
            aktuellerStatus = abgas.brennerStatus
            startZeit = abgas.time

    if aktuellerStatus is not None:
        BrennerStatusDaten.append(BrennerStatus(time=startZeit, status=aktuellerStatus, period=AbgasTemperaturDaten[-1].time - startZeit))

    print("Brennerstatus Perioden:")
    for status in BrennerStatusDaten:
        print(f"Startzeit: {status.time}, Status: {'An' if status.status else 'Aus'}, Dauer: {status.period} Sekunden")


    for brennerStatus in BrennerStatusDaten:
        if brennerStatus.status is True:
            BrennerStatistikDaten.gesamtdauerAktiv += brennerStatus.period if brennerStatus.period is not None else 0
            BrennerStatistikDaten.starts += 1
        else:
            BrennerStatistikDaten.gesamtdauerInaktiv += brennerStatus.period if brennerStatus.period is not None else 0
            BrennerStatistikDaten.pausen += 1

    if BrennerStatistikDaten.starts > 0:
        BrennerStatistikDaten.mittlereDauerAktiv = BrennerStatistikDaten.gesamtdauerAktiv / BrennerStatistikDaten.starts
    if BrennerStatistikDaten.pausen > 0:
        BrennerStatistikDaten.mittlereDauerInaktiv = BrennerStatistikDaten.gesamtdauerInaktiv / BrennerStatistikDaten.pausen

    print("\nBrennerstatistik:")
    print(f"Gesamtdauer Aktiv: {sek_zu_hms(BrennerStatistikDaten.gesamtdauerAktiv)}")
    print(f"Gesamtdauer Inaktiv: {sek_zu_hms(BrennerStatistikDaten.gesamtdauerInaktiv)}")
    print(f"Anzahl Starts: {BrennerStatistikDaten.starts}")
    print(f"Anzahl Pausen: {BrennerStatistikDaten.pausen}")
    print(f"Mittlere Dauer Aktiv: {sek_zu_hms(BrennerStatistikDaten.mittlereDauerAktiv)}")
    print(f"Mittlere Dauer Inaktiv: {sek_zu_hms(BrennerStatistikDaten.mittlereDauerInaktiv)}")


def sek_zu_hms(sekunden: float) -> str:
        sekunden = int(sekunden)
        h, rest = divmod(sekunden, 3600)
        m, s = divmod(rest, 60)
        return f"{h}h {m}m {s}s"

def plotBrennerStatus():
    global AbgasTemperaturDaten

    times = [abgas.time for abgas in AbgasTemperaturDaten]
    gradients = [abgas.temperaturGradient for abgas in AbgasTemperaturDaten]
    temperatur = [abgas.temperatur for abgas in AbgasTemperaturDaten]
    statuses = [abgas.brennerStatus for abgas in AbgasTemperaturDaten]

    fig, (ax1, ax_grad) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    ax1.plot(times, temperatur, label='Temperatur (°C)', color='green')
    ax1.set_ylabel('Temperatur (°C)')
    ax1.grid()

    ax1_right = ax1.twinx()
    ax1_right.plot(times, statuses, label='Brennerstatus (1=An, 0=Aus)', color='red', drawstyle='steps-post')
    ax1_right.scatter(times, statuses, color='red', s=15, zorder=5)
    ax1_right.set_ylabel('Brennerstatus (0=Aus, 1=An)')
    ax1_right.set_ylim(-0.5, 1.5)
    ax1_right.set_yticks([0, 1])

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax1_right.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2)
    ax1.set_title('Brennerstatus Analyse basierend auf Temperaturgradienten')

    ax_grad.plot(times, gradients, label='Temperaturgradient (°C/Sekunde)', color='blue')
    ax_grad.set_xlabel('Zeit (Unix Timestamp)')
    ax_grad.set_ylabel('Temperaturgradient (°C/s)')
    ax_grad.legend()
    ax_grad.grid()

    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    brennerStatusAnalyse()
