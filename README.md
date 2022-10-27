# Szakdolgozat

## Cisco DevNet
A Cisco DevNet használható a szakdolgozatban bemutatott szkenáriók/hibaesetek tesztelésére.  
A [DevNet](https://devnetsandbox.cisco.com/RM/Topology)-en válasszuk a `Cisco Modeling Labs` Sandbox-ot.

### Kapcsolódás

Az email-ben és az `Output` fülön megjelenő azonosítási adatok segítségével kapcsolódjunk az elkészült Sandbox-hoz, [Cisco AnyConnect VPN](https://developer.cisco.com/site/devnet/sandbox/anyconnect/) segítségével.

Példa kapcsolódási adatok:
```
    Lab Network Address: devnetsandbox-usw1-reservation.cisco.com:20164
    Username: radokrisi3
    Password: EKNPTXNX
```

### CML elérése

A CML a `Cisco Modeling Lab` nevű node-ra kattintva érhető el, ha kiválasztjuk a HTTPS kapcsolódást, vagy egyszerűen írjuk be az IP címét.

```
Address: 10.10.20.161
Username: developer
Password: C1sco12345
HTTPS Port for CML GUI/API: 443
Example Connection: https://10.10.20.161
SSH Port for Console Connections: 22
```

**Fontos! Az default Small NXOS/IOSXE Network le kell állítani a saját Network indítása előtt. Különben a hálózat nem lesz elérhető** 

### Router beállítása Cisco DevNet-en

Válasszuk az IOSv routert.

Elsődleges konfiguráció:
```
enable
conf term
hostname R1
enable secret cisco
!
username cisco secret cisco
no ip domain-lookup
ip domain name ciscolab
crypto key generate rsa modulus 1024
ip ssh version 2
ip ssh server algorithm authentication password
!
line vty 0 4
exec-timeout 720 0
password cisco
transport input ssh
login local
!
vrf definition mgmt-intf
address-family ipv4
interface g0/15
vrf forwarding mgmt-intf
ip address 10.10.20.101 255.255.255.0
no shut
ip route vrf mgmt-intf 0.0.0.0 0.0.0.0 10.10.20.254
```

### Konfiguráció mentése
A DevNet laborok 2 napra foglalhatóak maximum. Ezután törlődik és minden benne létrehozott változtatás elveszik.
A labort és a Network-öt lehet exportálni. Ehhez az alábbiakat kell tenni:

A `Nodes` fülön jelöljük ki az összes eszközt, majd nyomjunk az `Extract configs` gombra. Ha végzett a folyamat, a `Simulate`˙fülön letölhető az exportált Network az eszközök config-jával.

Tipp: Néha érdemes lehet kiadni a routereken a `copy running-config startup-config` parancsot. Láthatóan ez nem előfeltétele az `Extract configs` működéséhez, látszólag a running config-ot exportálja, de bizonyos esetekben jól jöhet. Például debugging miatt leállított router(ek).


### Konfiguráció visszatöltése

A CML felületérere belépve, jobb felül kattintsunk az `Import` gombra. Itt a korábban letöltött, kiexportált konfigurációt kell kiválasztani.
Ha minden sikeres, jó fájl került feltöltésre, akkor meg is jelenik a Labor a listában.

**Fontos! Az SSH kulcsok nem kerülnek exportálásra az `Extract configs` által. Ezért lehetséges hogy importálás után ki kell adni az összes eszközön a `crypto key generate rsa modulus 1024` parancsot.**

```
ip domain name ciscolab
crypto key generate rsa modulus 1024
ip ssh version 2
ip ssh server algorithm authentication password
```
Innentől ugyanúgy tudjuk folytatni a munkát, ahol abbahagytuk, amikor az utolsó `Extract config` és `Download lab` történt.

### WSL2 konfigurálás
Az Ansible nem fog menni olyan mappából ahol a fájlok jogai 777-re (vagy valami túl megengedőre) van beállítva.
Ez az alábbiakkal orvosolható:
/etc/wsl.conf tartalma:
```
[automount]
enabled = true
mountFsTab = false
root = /mnt/
options = "metadata,umask=22,fmask=11"

[network]
generateHosts = true
generateResolvConf = true
```

## Ansible
Az automatizáláshoz Ansible konfiguráció kezelőt használtam.  
Az egyes esetek playbook-ba szervezve találhatóak meg a `playbooks` mappában.  
A playbook-ban található play-ek nagy része ki van szervezve `role`-okba. Ezek a `roles` mappában találhatóak meg.  
A különböző változók az egyes esetekhez a `vars` mappában találhatóak meg. Ezt általában nem kell közvetlenül használni, hanem a `playbook`-ban a `vars_files` szekcióban kell megadni.

A `playbook`-ok között megtalálható egy speciális `initial-network.yml` nevű playbook. Ez mindig alaphelyzetbe állítja a hálózatot, helyessé teszi a routerek konfigurációját. Ezt kézzel vagy automatikusan minden eset előtt le kell futtatni.



## Egyéb konfigurációs beállítások kliensen

Mac-en az alábbi paramétereket kell beírni az SSH működéséhez:
/etc/ssh/ssh_config
```
Host 10.10.20.*
    HostkeyAlgorithms ssh-dss,ssh-rsa
    KexAlgorithms +diffie-hellman-group1-sha1,diffie-hellman-group14-sha1
```

Az SSH kulcsok minden deploy esetén újra lesznek generálva. Erre sajnos nem találtam jó metódust, hogy el lehessen menteni az SSH kulcsokat.
A probléma ott van, hogy a kliensek letárolják a ```known_hosts``` fájlban ezt a host-ot az aktuális kulccsal. Következő deploy-kor a kulcs nem egyezik, ezért el fogja utasítani a kapcsolódást (ansible is).
Ezért az alábbi módon lehet kikapcsolni ezt a host-okra.
```
Host 10.10.20.*
   StrictHostKeyChecking no
   UserKnownHostsFile=/dev/null
```

## Jó tudni
A CML-ben található Ubuntu desktop talán a legjobban használható (legtöbb csomag ezen található meg, friss Ubuntu 20.04).
A konfigurálása a netplan yaml alapú leírással történik.

Viszont a host-on megtalálható interfészek nevei nem egyeznek a CML-ben láthatókkal!

**Például a CML-ben látható ```ens3``` interfész az Ubuntu-ban ```ens2```-ként látszik!**

## Network Analyzer
### Telepítés
A programnak szüksége van bizonyos modulokra a helyes működéshez. Ez telepíthető egyszerűen az alábbi parancssal:
```
pip install -r requirements.txt
```

### Használat
A program indítása:
```
python3 ../ansible/project/initial-network.yml -s 10.0.2.2/24 -d 10.0.1.2/24
```
