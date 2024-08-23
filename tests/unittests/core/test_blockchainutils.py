import hashlib
import time
import unittest
from unittest import mock
from unittest.mock import patch

from mongomock import MongoClient

import yadacoin.core.config
from yadacoin.app import NodeApplication
from yadacoin.core.block import Block
from yadacoin.core.blockchain import Blockchain
from yadacoin.core.config import Config
from yadacoin.core.mongo import Mongo

from ..test_setup import AsyncTestCase

txn = {
    "time": "1634248782",
    "rid": "",
    "id": "MEUCIQDapuhma9ujBepNN02olXzjUMf7RTEpeQfUb57LsGyWGAIgaTsySLvgeVtS3wXqtcEolBS0j6+FK8ObrSFZOLUgBoE=",
    "relationship": "",
    "public_key": "02c786e8be16900051e059476e3fa42697e41dd9110c85a61c5cc17e15dafda90a",
    "dh_public_key": "",
    "fee": 0.0,
    "hash": "4431441e275bfc82115bc04402e71f2dc04d598c6f9905dfdd7bd274fcc34a8c",
    "inputs": [
        {
            "id": "MEUCIQCmqmnCcMNs6qe2fqcgEoMVdCzmuzNled9v4o2J8NS3rQIgWUC0Iybe1zREmmJOu2KZGNXbCNtKS9iDknVqObxUzhc="
        },
        {
            "id": "MEUCIQDwPf3oq+AueUkJlFUmJLoo51Hgr6sU2ycdHVKK1zGHrwIgbUXJVPOiw7tQkVM09udvzUs0bVO1lEGBfEz+mhTXM8s="
        },
        {
            "id": "MEQCIHFa/npfRO/C96DztzcOWU6RyqtjYXJqQeekTkPg6GljAiAg8itlk30F5bfp7zIwb1QhfvIWZOpJNjR3YDZmXtXRzQ=="
        },
        {
            "id": "MEUCIQCPKyuIgvrTCGIKx4R7FwlygzKHPg3FsW1ZnE9WhhtLpwIgLAksdV3VO2JvHanilb3uhklipLcfN8+kkOTguGxRGFs="
        },
        {
            "id": "MEUCIQDQ8vx226UbsL/VHOrWI1knP1EA/qajAU8P+9AdA1HBoAIgHQOxCwvpuJ3wpu+8279TqG0nHVR8ZlDZS3+y92t9H6I="
        },
        {
            "id": "MEUCIQDsieoXnrMz3Yy0nk1HK48rwGa1X/xftBYAky5ioZb+NwIgRy92IMcpRS8k3tZd4dS+qbneGit2AReqbR9I49VVTvY="
        },
        {
            "id": "MEUCIQCHxptH4/azupwHx9hSkpl/kD+zIK7iuhmyEKiYRIoSZAIgcn2Zr2R8c4GP026EmPfbxjarsWDYG5tOVyL46TYxWas="
        },
        {
            "id": "MEUCIQDT6iz8H4RCOPQQl8LaVCWATrPf1xuZEQ5uNairwuGqUAIgMoh5l6PUhQY/GrhqgOR6HY+X31DBHEa3nF/Q4lIMlKo="
        },
        {
            "id": "MEQCIF3Dnri00PIrq4QTbxdylVwXm4alrSs9h/1CtmnNj/neAiAyjDsEwwpsWjw+DUkj6oD8HKp6wPT8VFw9VZGad2JJ3A=="
        },
        {
            "id": "MEUCIQDoe+QKx6tGRw2JXPIhKsV5FuyCR73Hq40MIt8YsFA3VAIgMhWws5sJ1z6XhqpPc5/CMR3fwuC+gzo9uiutfVIa67Y="
        },
        {
            "id": "MEQCICjKROnN/eDm4/kLQK8YMeuRhMuAv0EfJFKIXh6YLcy7AiA5zkTpM5ZjrUZRAl8ZrC9NLmDgyPed1sGy6t7Grlm4ZA=="
        },
        {
            "id": "MEQCICypoe7PF5coGck2wMC0nxR06Y6QT1rC+TbuYug8qY/VAiAXyQGgD4XXkjePmSzD/AXqBMEK5VTl1lkKd5HfXzFWOw=="
        },
        {
            "id": "MEUCIQCJgliQjNLwB7W82jTN/dlj9qTtBDt5/0OpSHyNNG0KpgIgG8eExEAew8MGm5nZd4BBo/hSB+aen2qF/VjJRqhr3t8="
        },
        {
            "id": "MEUCIQDKqwnTwJnxulGS1qOLRGSORWN2BaQks20CYBQyPbD+dQIgfCIDS9Q5jhn4bAvVXRAwd8bWk/yKAaO1Jf0B4olxzfA="
        },
        {
            "id": "MEQCIAy4Q6sxFdh39LRjA4QJCiIIkXyDYbBJ+fdW6ogLhK0yAiBDgnmbompROW4/k0iCPIDufg2IoFv8MtffcpCP8PgUwg=="
        },
        {
            "id": "MEQCIExY1SaVEXv76Xn99HfFIU03kulWo9T5C9OWTkTZnmmxAiAlR4XDYcjU4bl67DkyY6yulBy+cJOvfbEDakhJ82D0pw=="
        },
        {
            "id": "MEQCIERndRseBZHr3n7i2PVV+G1UmS85Y4DZ/HMRwlBWVT4FAiBOCeIEySmTKMQKSIUzG0ZlcHTDO6dftZVLaFmFJPkIaQ=="
        },
        {
            "id": "MEUCIQCTDTc6vDhbpMaRgPAPNIqC860Thb0Ugq9gq+59fVSEZQIgQ1LYOkj2gIo+1/kAXWDSlDm7WtiL6FCYYSRofYKbtX4="
        },
        {
            "id": "MEUCIQDduFUOZfGtgRqk67XxbP3rFdARgb/dubr3aWpTLVW3GgIgZShYUW6kW/iW2zmmul7clAWBYsayCDg45DwxZpjyInI="
        },
        {
            "id": "MEQCIBsz/rYAW7d19//12Eo0iAeP8jXqIJ4lkNUY+vOghXSGAiBwqenxJGrHiDBvlUbGPHt6wYqA6CJ7q3YGSHcHTCVgRQ=="
        },
        {
            "id": "MEQCIFmRiMMBGtoBo1Fyo/+z8EYYiwo7+LgHEYlBxPROT9woAiBuM5zyV/vDpxZ2yN68cSwwYF1d1P4xixMtdy6U0W+Fqw=="
        },
        {
            "id": "MEQCIGTg+l/fA/DzVv1K/oXh2u+WYvJ7PiRCNjSwsWaQFivpAiBeGLR+jMkwqQkW6iBveTYV1ehySXQqNC5h4pdW8M8UkQ=="
        },
        {
            "id": "MEQCIBz1J98/UGgKkRhL3+wNvtv7t05NyNPErVKgcx72/72LAiBdGyZY46AXSI/ncxa3ZjOSPSXQNuaIajMWHOJvP/zhvA=="
        },
        {
            "id": "MEQCIDqo9zZDnftwSWxGHBr+itTrJe+B/1wKp1hEQALUjGEGAiAqG6bjGZVrgZhA9fcA+m+R4vZiFSUcQ2wLckoyUpzF1w=="
        },
        {
            "id": "MEUCIQD9w9M0TAQZMx6qGezx4opsUquZ5Yk/IVIiYC47RHYzVAIgeR8VP3IFdY39zVxEJuAkHgBG6esUwwxJOnQCXolJBrk="
        },
        {
            "id": "MEQCIAOd/10BT8nrEVxqkiSyHVHpcrIPGKxsyu45+YLlN+R9AiBKpsTB/sQ9CvZLhxq0gvLcCO2LbYiQ9Ut2Y9/XL69L+Q=="
        },
        {
            "id": "MEQCIHDlfLpzD9pn4KwaLeSKTTVCY33foe2j4WP5k7VjLAzfAiAqmjjuCJXY6dYIBCyuylXtOz9YemhkGBwrMvk/x84jOA=="
        },
        {
            "id": "MEQCID0l49gmju3Osv07SqpfcznP6NzIc5IZizfnQRqHXnlnAiB2DZAAE5biGrfjwRlzuMtXAXl/VU5y7Jf3b5RzoUmwPg=="
        },
        {
            "id": "MEQCIFmQ7Wyhy0bCWecBrU5uGhEtqbJ6o2lFjeZ+KjFIjsMJAiAyViSXG9ophb9mhY8ruvrpfmBlp2OAHwoWt946zthYsA=="
        },
        {
            "id": "MEQCICC0nO1GNvPjnFYDeVSiEHe8z8fUqPnjFlgHvsVSHx+LAiAeEHJfb4frTcf3oPiaRPUCWdPgNdORxiuhCGXZ4DcU0Q=="
        },
        {
            "id": "MEQCIDjF2UhN4aCHM3Wnod8wkprft0mN3KU2eX8M8cYWQp0UAiBtOQ31kGRkb0nkWbn1Yu832vMBurf4eHRMSlknW65FIQ=="
        },
        {
            "id": "MEQCIE04yUTU4GtyFiIjbz3z5sJAqVCu4fq/Uk/erKDbyenWAiATtqbyJrM5W4c0XL1/1ttpWokQDHsBGuhVXll1qkPD+Q=="
        },
        {
            "id": "MEQCIG/7w9T97igiq47zvsnpdmSunRDqzKhHiW6Mu8vXOFglAiA/I0+YOplhp37BSdM/BZuOhqs9FqvjLeiEqGTL9ksd1A=="
        },
        {
            "id": "MEUCIQCC8EmZ1qwLu7GvVb1Xj83tvlf+a20eIPneiPGONAsbPQIgOZe2sbyY+yP0aKl1aUkEZcyS38SM9VkPzbkVvasCYd4="
        },
        {
            "id": "MEQCID3tz1sSbXlHBuNCvLleED35wIRDCIGl0rfOQjSQpssBAiAaNxi8UuCDcq3TQp1cS5y7LC5/2ZYVFg3N3x6JBg3/yA=="
        },
        {
            "id": "MEQCIHxXZeRJSuR2ozmdt+vAlpc8ZZ0wMOt+coP7we0/mZsjAiA13CPYYfNWntXcsvpgVurIy7gqfXl9aDvUD17K6iDb1w=="
        },
        {
            "id": "MEUCIQDwQeE3QavtDmanrR+C+k6LNlFDGdMexE2Bvnb2BcSaXAIgbkfNXCHSlG8yccg18uFYVF6pp+vm1rBy/ffVNrj9bt4="
        },
        {
            "id": "MEUCIQCGgwj6HXFspQvtQAGq3wSb9PcXt/4zg2Rjcuu76VJhXwIgWGKhxCAkl/rK2qBkIgIUxSWLK27DttKkU+pKfd0l96M="
        },
        {
            "id": "MEQCIH0GfjP2TA8jHqs24XVUADNAEgcPnAR4g0cybFYSdblPAiAkH+yg5hZhZQmbhDUty0VJfGgEFmNB5YoGVMwM32lhFg=="
        },
        {
            "id": "MEUCIQCq6tXu5XTkyj39qcs/DwHKF90/ANTBb01PNdCGYaUo5QIgdoZRnAM8H0XnEWz+JZqZ4Z+IFdrqlLU0slaxVB7mtwI="
        },
        {
            "id": "MEQCIBbnYy93dsed1GPTQc5s9OJa3ZxgTut2dcdF+0srBB0GAiAI5DXqwr7Cso/EJ74mAkomByAG8+9LrwntW87bzXC8eg=="
        },
        {
            "id": "MEUCIQDz9u0j6hj2IScdIcttrrd0iXfdpXTg/4chR3CzxEx8RAIgPlWy2nzNxdP1/zzR4ASOG7+UXuClUe1hZ1/CdKENR70="
        },
        {
            "id": "MEUCIQDbtQLyJkIviOyqKfCbpfSa596nb1cdORH/W+QKhfD61AIgV31kJzQZkZnb6ZLJr+eHaUaWwu7EkBXs9NM/Cl5g7Xw="
        },
        {
            "id": "MEQCIGqaWlPTR3kx2TvcKQZOiWXJ4yuhC6MbsvoSJMlnEhErAiB6yisAAZeaxptQG9gMyvbCg18oNeC2KaqRMXcCB0UPow=="
        },
        {
            "id": "MEQCIEzf+mXMCkrmoTW4vDUCjO/XpZ1MYeot0kIN+bEBw5sHAiBwWlCX8OcFBtrJOFSPIuxz6td2C1R5cpHOCeQoMTTJig=="
        },
        {
            "id": "MEQCIA4eDiqT5+LbqITHbeYa89AZPQ1HVoVAHdhEBc9Yv9IwAiBh+VH8Naup6FPfWZ6KPR1pnCxJ5nUu0ckN6s1ABCVbeQ=="
        },
        {
            "id": "MEQCIAzAHWf6xAHIwcwIQ0JKkkJTiSrQ/djyqbwodC8LIq61AiAHPxWrUWiXBznkT8Lfm0esj00BaO1Mdm6RganMTncIJQ=="
        },
        {
            "id": "MEUCIQDOBwO0ZtSgRQco0EkYuvlIEDzdNoDcGI+pnwQPuvulNAIgc6a943BykCtoK0TlCpZpmD8HTpYDe0XcxaevcbZsEkM="
        },
        {
            "id": "MEQCIATbyQ7QLRy2A+m+1xZiLYN95CKMTO/akjGolalrQ+T+AiBLeouo1vT4P4AFrbDtpyyBC9k5RLyphi40KUD0iO/wig=="
        },
        {
            "id": "MEUCIQD/MY6cNn41UfFd5zFZ+jfPRIl0gRgfvgMyr/DDuFkdvAIgD54mrSzCiGuARA0aq1mpCg7CiB7duMFC/tChs48zPXE="
        },
        {
            "id": "MEQCIH0Fb/0cfn10MwCHN8zwNbDSMt6YVsKxayk6BsPKlRa6AiAeV85RsvraImfxUAZvNfBsQP2O0R7qaC+gNK4xeXJMUQ=="
        },
        {
            "id": "MEUCIQDvGC7dIARKmTJJo1QSEvjM3yp7DZKrdIsvCdChQURQ6QIgdbBdBMHKvCwLp+LIfoN5pPuOMyvzj4F6fJreLtKVlxA="
        },
        {
            "id": "MEQCIEC47LdVq2Or2+vlxQ3c9klBfsptsFuc8KstKW2v1JboAiBu9ShqAQrH+DrtRLyxp+dMDB4CgmmhA01k7utXTbiJVw=="
        },
        {
            "id": "MEUCIQCT740gBB5+uSp1M3kHZaikIT8OItjklfo5IQnca5jlkAIgJ3ml1qASD9lLZL1oOPOPRPtaUrrnKZCr5gb3OSabFXg="
        },
        {
            "id": "MEUCIQChFFELXZmx0vuj/LqsKr/QAIqTF+TrkIEN0qlBzYoTRwIgRDrp+IEbzic+XRglBMeEOLBIOxKlaf0GFVd3dh2VIlI="
        },
        {
            "id": "MEQCIEhcTAEBMGRp2oWV+1G1Xpw48j4Eyzp/8vUHGghRuATrAiAtIZ5vd/lCw0DnPKB6aQ+G0fwSKDYGDLlx1GtvHMUmlg=="
        },
        {
            "id": "MEUCIQCEoKKSMi2x1DQ8rOrstGVOc2Xs28ArwRDZy0ZSPeDh2AIgGankxfwK54KWJqxJqXgsHwyGXC4isd0czJ7r2cnOO6s="
        },
        {
            "id": "MEUCIQDkQgopJiLTy124o7bWNn80Of92NrEiwgYf9yiXlnrzfAIgety2fK89DATDiRhDzV/5bera+VlMkaKyBsR+eP89vxc="
        },
        {
            "id": "MEUCIQDhaR3+uWpkdiC0Sdn/AfIOHQ/LVS6IBrgB/JkBkk47rQIgXZJ+Koan7pPG+PN5iMZhSA/s99eO3BTMgaY55AOiUqE="
        },
        {
            "id": "MEUCIQDFhKXWYBjLfz8cGFYtiL5Ws1M374NJcfOH1lZRntu3bgIgCKaPKdT6ZKQ3a9OspFQPWwQVlwHYVSTPQX4m+Mi6f7s="
        },
        {
            "id": "MEQCIEeiKLxYXB6diT3UVJCmrCbYTDs24J8GdzrNK4RGk5KUAiApjtAVFX13doMY3y5UNQPKecpKwOqsBPckA9ShLK8IYA=="
        },
        {
            "id": "MEUCIQCDJTyvzSqBKigf9jJt8GjPhG6BGRZZza6nHIPoufZXkgIgR4f5EOGy4J0KGsAM9vJqGVn47Z2H36fVX/Jzqxjuq4g="
        },
        {
            "id": "MEQCIEPOvLe6qLo/RHMtKVQXcdiWxZ/IrVjYGsLv5ociyr/zAiBl+yJRqvOsHrsBVcRYeskLWxr8Q370nKQuuGICQTD6Uw=="
        },
        {
            "id": "MEUCIQCIjm1786tKeqqoPXLGB0DLP27sLp3ffE87Ag11prkI+wIgC5aPy1p5WxsAgTfsTsvPv/6eGmN3eXV02NTYf9Vhj2c="
        },
        {
            "id": "MEUCIQCye+CUgsPPo5Hx1JHFsfaRvR7yYuLAXqZOXpx0cv7LWgIgeVTpp3XiLeiVO/QhS7qbuuTlzGnz7TCSo7XEGVo7o0o="
        },
        {
            "id": "MEUCIQC+8nN4geTFPkpsuDNNrz1XzZYhCliNN+bzgiogWqta9gIgH6A+XXGx4CCRE9zxYHZjfs5iC0q2exkyoT8rs/qZtvs="
        },
        {
            "id": "MEUCIQCbJ53XAkf5c6aWczXCREeN+yeLj9i0OhkekFQeFJb4NAIgf9bZoOGpg5Zgl+tVsqrS6TsLiL1t5pgjfC1zXPg+tOA="
        },
        {
            "id": "MEQCICG3onekfD4Zb6PjVENqVCACz6LzYvt2Ewfs79b0hB6cAiByb/dBhCKQIyTKHnHnwQMJNiCXU+E/JZKLLjVVBl2xiw=="
        },
        {
            "id": "MEUCIQDzf/HDQV/X4kuy8eUQn5mx//MtJ9BZyI+eeHz6pMEquwIgC6j6vnJ+hMm16yu84BBQehSNe5fWshPUOU008oHE+tE="
        },
        {
            "id": "MEUCIQDdlQtSq5Hs/CQ3QGhGseCSjOUhLEVMzUEFD7Ry3TMOfgIgCgpiSIT6fNOGPGTNHznenzW+dgEG1GjCPR3NKro1wZU="
        },
        {
            "id": "MEUCIQDEvF7fJADWFJ0TcjlUAICFgewjlxZgVOV4JkzkaK2WuwIgEhy2VuyawuP9Ms50EmX6VR5+DGy2HUkO0EZwj8Tv3M8="
        },
        {
            "id": "MEUCIQDhYp7OV6M5GNgG4womg+L/jOgEa3+l2DFYgEz2yj3ChwIgcWPBiwTvVlBrsfwmwB535kImPTf8EEuLpLVXrV8B2Ro="
        },
        {
            "id": "MEQCIBQ2esd7M6SmyXBvXJtOvVzFaDIjV/DYcKYQ+FpDXijrAiATrWMx3TXUcZ1L4fE+54wD60VgqXFaKvyN04WNiFQWGQ=="
        },
        {
            "id": "MEQCIEGSk1+VI7kUj08mcU8tSa7IVNCNbbwLNvj/rj2hWa3bAiAS9WfvDPM9/T54IomILd7OpsB72uRH1lImmYgsUgAXow=="
        },
        {
            "id": "MEQCIEmaikVfK/Sb5K+tBYVSKO+6OQnD1vuIsdUY4toinGmJAiBl7RDw66HPehqrn7Ew7Z96j6LNnqKHRpcBU3tSfFZ6EA=="
        },
        {
            "id": "MEUCIQCU/kpdFS7Mdwka9/2+/sVo9nsu3fG/vH2WKwl0x+PrvwIgFVDQPZ9EvLmPJCR0mVR4EGYuRLml4aKPl8gMSdj5RlI="
        },
        {
            "id": "MEQCIAObR+s67sZIXul+Pc73Q9LRoRPAidn6XioBd/qTiggbAiBFPNtk24PKzcYtvKPJMqtEMGJ/WlKLQ/nhUk0XLtbWHQ=="
        },
        {
            "id": "MEUCIQCYJIT0zobAdskyXXofnlptvORY8Vqp2ez+69F0eaVHbwIgDJIXKUifpuTBpsI2CPis8svZzmFC/Y5mL+p6sLpxbPc="
        },
        {
            "id": "MEUCIQCp0vNqDBLq+2fTdGX3MJoam1mpC1w57saXdhzSjiWMigIgKFK7IroNoHoUVwBAAZ5Cdc5WueW9XhcZQySVfAPhtdk="
        },
        {
            "id": "MEQCIDBW9g21Z1j7b503Sp03FBNhPlCLFXsub0mVyLNTsLzkAiAZdOhiGoQ2Tpj84ml759XRzW5s/y6O6A5NsAHA7CoQ1w=="
        },
        {
            "id": "MEUCIQCoY60EvEpBxyqvSdJWBfx/oliCOJ+jOB18/m81pMLx1gIgNXegMx1hjLhWQsvnyUeI0ZBdea7Cv33Mqbrq4Lkpeg0="
        },
        {
            "id": "MEUCIQDjj5Jm5wj16embruOt6TKubrOpV5dd3wzX9zsbTV8ucgIgROSe3vtUOFOV0JGlEdXYI8qreo//1YZVSeg/iEROOnk="
        },
        {
            "id": "MEUCIQCTkk8N3cl0ZOqtevXshrJeEx/APc6fssPWGOaNH2DjegIgeHrs98t6g/cAccsVXOCkMuLlMTD3wpDmmNtLbG8esaU="
        },
        {
            "id": "MEQCIAEt3oX9zAlLv98liHCgGY2p4yMeNHqKYMOKqx8rnGPkAiAT5MHpqqhVRYQVCAcTy5ZgZL/9O+37RNVADp7eTcGsig=="
        },
        {
            "id": "MEUCIQCLNWoK83sNvUPaEOwxLd0kmk4rUY5e/s4eikFs+uXQbAIgMEmMA5bbWxjowOpQ8Vd8KggtYKn5abCSDNWgfx6iR9k="
        },
        {
            "id": "MEUCIQDBrE3zABg5WpsqwgarofQQk5axLUz63brl8E5bRevS7AIgICuUaa0DzTvOQS2Ep0RwU/1B+QD4OIFa6ceqtCoJecg="
        },
        {
            "id": "MEUCIQC9VQGZtRwPpVyy0M6dI8YIayAvpto1HrNj8PJCClOPugIgRoPv2JKJ11nQt2gGSyhS6CU44DZFSL3hpopgwdh7axU="
        },
        {
            "id": "MEQCIEzBhTtkYJqnoX8meBH2P2RfHnz4hthy+QY1thMYiVtlAiAP3r1u3KBgrAJe2orZMD1XxnHuJzvCaxZuJBEwuOVrJg=="
        },
        {
            "id": "MEUCIQCl7ux9UACbkFs+VH+wFDiSIsK0L3zp+6dvMUNKHZymFAIgSHmV9dayE/nudX5eTnqAS5oR9c+12uC6GGKDG1HZDWU="
        },
        {
            "id": "MEQCIH6rAcDBUPDvhmyPPehyHPChdj9c8mxtSIv6WNsInd1jAiA0hQX0YTToxCXrnM/MoNNTIP6HWOOTp2VvM5bJ+9gWLg=="
        },
        {
            "id": "MEUCIQCLri94+M8qShfxRGBYsXZxixxOLg4LCq84/Wc5IdBOEgIgW2ZSddYqMrM+VtmZj5iA3GQrf87ae24EF0OJToo4yjc="
        },
        {
            "id": "MEUCIQC1+oi1EZrl3cRXOEXc/5tevog88J0C3cRuVXqrg1Hh0QIgGot2rp0gtmq2QPdPTIHIIiM9JS2IvEGzF0sGUPT8c50="
        },
        {
            "id": "MEUCIQCdOruzObEbJxvMFKCM57UUOPSoy3ckz+BMvAL5iN12xAIgOe24FGkczWzjOFJhL8Wp1xA+/OPX+U9oXvnwL+O8TAM="
        },
        {
            "id": "MEUCIQDOVZSThMMv9HgUrs22vn/OA0vsyahH6/SbhD+P5cCsnAIgaGXlsCCK7wCrNLbqAlM2ovZwi8gsJlhBRHhFCvv/pCw="
        },
        {
            "id": "MEUCIQD80PFvOc8y6hFHKT8Fn7Uuz/vLb6wya3nrYLskdOuPfgIge6iessXRMY7OCyKMIeUYABMcZfopl49/TUFF034EmPE="
        },
        {
            "id": "MEUCIQDwjyFDBubFgwl+ilcbSWa6osXY8s7coscjt9NZc+9OHgIgWji0qRSn2zbfKHbLFa/CPBdJvyOOwVZ6rnprVi13bdA="
        },
        {
            "id": "MEQCIGqV4vP5j9T6khOE4dH5aDCjVKt1ouudYExir1N79N5rAiA90JscVLbjMGL/1iGrKZzLwTXKvcRndOj+SRH7bKZt8Q=="
        },
        {
            "id": "MEUCIQCZS3u9SREjHwu430bmEbO9LlgTRq60Vjvn4dIv2Rq7KQIgUthS3EjDEtSfMhJgggME9wQCWqgpicrPaiRqKtyA80E="
        },
        {
            "id": "MEQCIBxHqagzVhLYicO70HU2u8273B+Bk0bVVcoar7wMfR+8AiA6wynetUfCPjVzEpESNyzTrnXPmtETMiI3ca3/ZYuOZA=="
        },
        {
            "id": "MEQCICo2g4B6Vjwjp/nCCG4odpPbVWVSMG8+5Sm6r3WbusIQAiBe+gzFdsvq6+z/3COwHxFSIK8f5x7oXu+Ix0zdKtRi0g=="
        },
        {
            "id": "MEQCIEXDYVngCUL+p+ANWlwlZl/RiCS9iT+7ARe1RpH5m5NUAiA2QDT7H4Dgg9rVy058ykR7C5F8cGxg3bvE4VQMNkYWrg=="
        },
        {
            "id": "MEQCIG8TX4i40gYMO0LX1mzTSQpOmKi74JCm+m0EkQxDqemWAiABI1IozGIICbn4/JZCVBQkS36ogZ++loh398bi4W7B3A=="
        },
        {
            "id": "MEQCIEIxt58+p8RWcaPLWts7cDLfbcGbHXMg9tVE8ZEBx44nAiBvHvgiXyObHmN6VfBrZR5e5kj11JC5OlOobLrZwtuqrA=="
        },
        {
            "id": "MEQCIBzfv3bNkS5QPs8Dk8CWpwy4uLByeeTo3ITwWLNA1bQtAiAVtQWQZP65MdHM+ifZGzPCUsyoGGqm6T4pTa39o0lB4g=="
        },
        {
            "id": "MEQCIAURdLue3cKZ4KL5a755RcMq3/mLRAxDXnY1LRGkLNVfAiBxoFZGIWNvLoFDuBVhMVlfG7vB7yAuGKZcata4e7ianQ=="
        },
        {
            "id": "MEUCIQCryEYqfe6BshFS5L3xxblIreY7lgyBfIX1la49SNu9iwIgYdYyp/0J41dPwS+S2j9drhrykL3/qVLg15JXKqHP1M8="
        },
        {
            "id": "MEQCIBK4Pz0IxzVvnq2Yr0IomgcNYNIpDpvH66goBSpDtxT6AiB5MZdQnHqRzuRMn2mpb5CjdwuzfvqiKh9KLVR0rEaDBg=="
        },
        {
            "id": "MEQCIAxijhfX/6KenQdYbfs2nqgh2eN41dmE9WDfFzBiIECNAiASmnevdDXzZcJR98egbt3rTh4GvBzjXZreYXad6qwqKw=="
        },
        {
            "id": "MEUCIQCP++SJ8vRVw5CYJhctRo4hpQmPMxKktEA1lFgqc1XTfAIgDCDFy31anZqMhKW7paD1NDI7ig2+whBCKhPniV7jnNo="
        },
        {
            "id": "MEUCIQCtTICC+2zElZfBkYIN2Q6GSbvgznSaQOvYnL3ze0ElUwIgfrcC2McENeaV5rGcqelmlcoYMYbj5i5Hv2vMpqkfHNY="
        },
        {
            "id": "MEUCIQCTFWHZvaOa2x/mT4lGyo+x7uNB9BlMndT9VI5bsUorlgIgMHj00Vvq/AFx034toLqIO549VUV5b4OxuItR2RcSc7s="
        },
        {
            "id": "MEUCIQDSQWii6P2nbIwr3JUdqxGvYstGudmZ7Aw+8qCfPBw9GAIgKpvW35y4Ix+/E+AQpLrPKwrkNCLMTXaF6xXPZvnkiOg="
        },
        {
            "id": "MEUCIQD/7VJMDyzF5RYlfwFvqx9NNiTGPzB/joTvwytnlpOOZwIgFI0JJ4O2gMQhPCcy3CIG9i/CHKQ0hWptJvDp3r58pQk="
        },
        {
            "id": "MEQCIFhchu1LtsIQK/hVJ/Zn89ff5iZHfb6DvnvxBchMedQiAiB7bQGn2wdLviM1zJdFfXi+GZuIX1zAF/oxCBVS8KmtyQ=="
        },
        {
            "id": "MEQCIFvPuMrPgAfwWRR0/eIOqS60M8b3XfF1O7RDkKPSdvDyAiBZ25Tz9l/o/TJjgvBAWBRO3ChX5PmIS66EN9wkRLVCvw=="
        },
        {
            "id": "MEQCIH8+oorrE29h+a13W0Qo67Q5ID8Nld+XlETMyHLGQzTuAiBnTIKxSFX9q3sD3oKGbcD/IWmQHPTOZBKqjGxsvgvxFA=="
        },
        {
            "id": "MEQCIBV9WgsXZzHf3xct2PQK+JDRlmPbJUKmV0uO6NFKtVVhAiBi5Zuw5gbaViYLqy8mlQYBjcfvKoRvhulH/+u3c5vhww=="
        },
        {
            "id": "MEQCIFxigUkPOUqOOHUdLF70pJHffjG1EPc7y6UvOTbsRbZWAiA+3+/5UXYhpbKCZ9JrM5e3oN8nm8Frk6VMmQVO1jnA9w=="
        },
        {
            "id": "MEUCIQCdKeHI25UUHf0PoM4qO1835uY/iSsXquFsQdvGqAC/kwIgAaP6C2AnautQjsyMNJK4h38JRNA+dFwQcoR5utPl2HA="
        },
        {
            "id": "MEQCIBCR4x6t2152bHBZvxPetMLS3V9F7wVSaDIjRpUJ+U+8AiA6bvkjl8CZSYN4kmEoT1P5OHahP2JX2ixmLw3NvRi3mQ=="
        },
        {
            "id": "MEUCIQCk15/TXw3eBnHjclA43e5Uu30iKt2Pz68RPVOtawTsDwIgLB2CCKiSC1KnMW8B4Zg3AQ/Dh0fGCUDe2U4bvsgvqDc="
        },
        {
            "id": "MEQCIHpKEd72QgoWF/zdGKRtKzAEic/kLgzyxohAJWFwZTruAiBWe9vM0RHOXBYTeeQSWtpNx/CBXc/0Z/ABOns6PXT5Ug=="
        },
        {
            "id": "MEQCIBvFeZb8ZUtQVe90kum3tjO6NteLvN6czSMNWhkzLb5PAiA4u6K60tkeel5yXn9GL+rPJJCPx9X5923hW/g46InJGQ=="
        },
        {
            "id": "MEUCIQCq680MPNhj2scEjuRVSDUaVKfo100zBI22wpBQ8FKpTgIgRYKuGK4xep/FniYjJfPhEgZp822fJXVjzuAnQJVr53Q="
        },
        {
            "id": "MEQCIBYBwKXc/Wip0GAz4/8d9BdNuL2SAvgiU106u2bRHFv5AiBVWX/DxfCtAJO2gk13DQrc3BEwwJWlbrV4o5LENyZjiQ=="
        },
        {
            "id": "MEUCIQCbmPQh+wCRUSDlHaEP3dNRN4k/xuUnZa9XmaB06NN9gwIgY6Ri9Mce7fI+xqmzEeZ/hF7yBU7RCjX3MJNunNzAMgc="
        },
        {
            "id": "MEUCIQDAkjg7bShnD0gt7FsiQ1vTDWj3+gYEjREpML1QKsnRyAIgOxLs4UJGIXHNiDvxnDD7c+YT8E3v0cydFu8Q3C0Ph84="
        },
        {
            "id": "MEQCIHgiJJuhMzSVNHdqVnMXl+zpHTr0C7/mqcvyzIpY+fqmAiAujXFtarCMjQbXNLeXr/dayi5IHZF0c9rRxhw1NvB13A=="
        },
        {
            "id": "MEUCIQCOYdcOG3fYn5DTJ233/rAL7rixGDtKz7ekmi/0B+GbiQIgA/8Qr9+wPkc2UykF5MklKAf1Oo8tqLlfkHCBSbPgQws="
        },
        {
            "id": "MEUCIQC8FUgA3Tg345Sk9Kfb+HlFoOTiP81SSo0zvgvEZOkmPAIgf4K6TF3ueYbRQIA49cjedsNuBs0SwbRAouGQ/CL3hGE="
        },
        {
            "id": "MEQCIDo+u09tSjJuSEK4GjSVeBvGr1bdc+2AMBrnZjRDa2GTAiAH7PzDQI6jzoSVYAzcNsCbhTi7B29EjFUISe7XEQPkHA=="
        },
        {
            "id": "MEUCIQDojHBLI8BuA8DO3qKQDxNN4vS2++ExAS49IR5BWG63igIgKC2QD5PveVfeENDA5d9cF1VWytaBVSC+TcFtYNPtGXc="
        },
        {
            "id": "MEQCIAKnvJ1kp6cALevGL7JAxukHy3mxEr2IGMr8CTHrVRm4AiAJoOOKNNRuRSGYMRENo5U4UzaUXUCFsAharthCt9HAeg=="
        },
        {
            "id": "MEQCIAajSCnNCoxrf3kwy9vAmOytQdK3kArI02zwK0E1WH4FAiAS4GzLnx03DpaMiU3l2wJDFLGyCNIcIbEFUinMLGl7JQ=="
        },
        {
            "id": "MEQCIGTsAW1PzRhZLrSdWLl3mlyFAhmxXqfxUS7sSzRBjfuuAiBwXBF924Xt0hDJgnbgvf/RxB5H1FxArlm2ayhOA6sDKw=="
        },
        {
            "id": "MEUCIQC5EWdJEKQ7iQo6vdPeJ3Jc3e0ba7Qx0XdG5c3bFzm6agIgJjTcrTT0dhjg1SVr9Lmdcsuv/st05qrzmMnMtq1Aa4M="
        },
        {
            "id": "MEUCIQCrvNWYAFXKQiLl4vVzwD75CtQbv36EY1n8AfRvvRIgswIgOONb4JWJMEmdIvI5JedKoZ4PNAT3JZipKAexWCfYsU4="
        },
        {
            "id": "MEUCIQC+Sk0GeDFVADjIF6klFXc0WgmAbkbjzEglnd1tbC0ZOwIgQzVh/BMAHEO62HwAdrYAfgD2MczD2ePDPi7jEnoaiG8="
        },
        {
            "id": "MEQCICv9yKULbD0kw+itl7/4LAnOSRWdfFAD1M6u9tMa89Z6AiAXgGiU5H4aPCH1uD+i7XLtlXwW6TGvHoSdIvsvbFjs6A=="
        },
        {
            "id": "MEUCIQDPcGdoETOfR1jXJiA03OEr7febxeGcKblDUavH+/4uUAIgEuNIADKYJeZLrjhd2qNtsURiu4JfsNxZTeQ51I9hnYc="
        },
        {
            "id": "MEQCIHTQP3qAM+ElcqdODWVhHuMeHYCa3PYMK1V17LO5W8xwAiB5Bl7qGQvX/i9ctFpXaliT4lz2hFvE8EvNB8Mfpyv2JA=="
        },
        {
            "id": "MEUCIQDVL2avpaL5IEg3rmt7eas9TiHL9rXwihjHgnJa5xeNbgIgSI1a9LDIZnnTo97OkZuzGWoCF5PLQXkoIQ3YYhS/q9A="
        },
        {
            "id": "MEUCIQCLhMHKFqvhSvH8xEJ5SrHw1hPTeNJWQU0FqdavcFMGpgIgel2Rs9NRy9qI2p3BLA3xSuWjHJVU+SEU8tm/EwEJQHc="
        },
        {
            "id": "MEQCIFcVKoO2KVMVAr/I36+E/bQlelxW3TAk+jgvksCnrHUhAiBl2lPQNWJFguRnUwuCjpUz+1pabKqzfqUnZHvbkXA2mQ=="
        },
        {
            "id": "MEQCIA6Uq/ROleSUqp3LQ/7qk2yjMVD3rAlzGZ1a9ZhsUObxAiAJYqtVDW0x3HiVvi+4SMWdBfXJKeN5qyIRakIQ9aJ8Zg=="
        },
        {
            "id": "MEQCIA2/g2mFMOvF2LfScwA4TzD5j6aRTrr1ySPZ0j/8F1afAiAJJdriLZ3M71xpr8aYpcLcAnOA/bBH7W4fxMhvcPrxiQ=="
        },
        {
            "id": "MEUCIQDVQ023t2m5xyg6XAYxW1Hcq9W5tlYXkZd2kXPaIOcb0QIgFJ8CCZMfNweMMkifG6qVw64t1sRYQvjZ0dPyjQzTz34="
        },
        {
            "id": "MEQCIBCdUaubpdaSH6BIy6mcCJ751qBKJQjh0lDUXnvqpeLqAiBlRMdjBGrl2OoTcJlvvQxPt3n8I4iGrABgYS3Nq9c39w=="
        },
        {
            "id": "MEUCIQCmEJ4nSg9RrD2uRjg0kYhzPXBXpGaPB3JOQDOtxhMqIQIgd1hxhHS9OBEGKN8Sa9vlZ0XCsM/8e5d+iU0gNnz7ij4="
        },
        {
            "id": "MEQCIBWBNWONtqFTBYxDzIRT50HRx5Y1VgkGp8h7SEZhO5GDAiAjck5j+HdMZ4oaLUwngNW2uw9XLPkB63LoQfFo4IQfgA=="
        },
        {
            "id": "MEUCIQCm1Osj+QJrRkzf62X82r6ECT6GQQLNjEUFg5IsR9C4xQIgbNWXBJKzTg8KD/KMJiGlqVPPJ+ojqKoVT1AWgL3WKZU="
        },
        {
            "id": "MEUCIQCI0yb5X/NvF2Z1gjIoeuIY05NX4/m6h5Yh3XjgHSqVCwIgb+B6uE6y3hPgRd0yAi2hltBaUUVs6i4O/Qps67SrBhs="
        },
        {
            "id": "MEQCIDTibnEXETFpb7pCNg09ndac6igbhhCDR3+L9TyM3UDbAiArn8uJK3kVSI/IlP2eTydB08PRV4oX6Gr0y1998CrIXA=="
        },
        {
            "id": "MEQCIGeKjlxdv6Tjo4XpU0KAUswB1Mb5tPwHE6TM4CGZYkRlAiAFPgovgDY3HWVZrvbxZ//ziDeI3PISKv2b0wBRyx3XYg=="
        },
        {
            "id": "MEUCIQDU4ec0sf1HfkSjecqz10RVsc+mNEzSjGPW69v2LT/0ZgIgfRd+PI9pm8OK6Ra8KJy6exCVstG3SFBP3RcSKhoia3M="
        },
        {
            "id": "MEQCIC4GR9dvdAllFfurHYmKJLc8wQrKLmXRpihgcSGrWZYyAiB/tfNwxEDaId+LyObc9e2piwZ72uBuqd9xL7rID6SLgw=="
        },
        {
            "id": "MEUCIQDwfOZQmbq6vBpf6lGbPenj031Pt4/9i66Usam097nl9AIgIKrNn4N+Yo+EWSj/7HaImbnHZP9jeWpCH75H+dOX3hw="
        },
        {
            "id": "MEQCIAdKrNqWTLe543Kv97AqxJrlp+MTeWY2iw+xz+qPnWycAiAWmSe2i22ZcV6B2vFDQ1IBJa1M2sgKB9M3bmcheHaSsA=="
        },
        {
            "id": "MEUCIQCzfkKs2f7lfW90y2PhXO7P7oJTCxjrdpbEb1KUcGH61QIgVPK12Q7zfff87LgxL4sqSsiT6nSHUMZ9xBo6d8/GEws="
        },
        {
            "id": "MEUCIQCj1xalYFvI8UeJ1UkqrkW7Z/lVNs/DowlVopulAHOkcQIgfGA59jbtlywbH+C72OxzfKj+KUfUpD+yCS2wXYTducQ="
        },
        {
            "id": "MEUCIQCAXgDchRvii92YRIvavnmo6uEz6f36lN4AOXzlXWDELAIgeJwy6XuyMYIpuuazaWCPYfkFz9w+PwWlVW3zsRydX7c="
        },
        {
            "id": "MEUCIQC4v9FZQBkPEuJbgaX5cn8MkVqKd4TqrcFKdC9TAKHDhAIgaMBJ04e8GIGc5POsdAJKPtgkV+MuJW1OPzSMEgj5IT4="
        },
        {
            "id": "MEUCIQDNIKjboMeM1H7SnCycq7FlpQ5c0m8s/UyfjFpMZ8VTtQIgVnjEp/A0Gj03R+X0Qce/oKnMhzLjLmzkcnRa6FXtl1c="
        },
        {
            "id": "MEUCIQC455QJNrXKK7IRq1gKJeNg9BVcI3QX0DC2CT1ln6n2yAIgEe/m8DXwuwlx9fBtA4wwgDCYdEKe4Y7BrML3ruVjYA8="
        },
        {
            "id": "MEQCIC8K2WJYcPg/+8NJ3VJDtWd3/drdAJpPTk1fdg0/ZTTJAiB5KvIdJyi/d2g5NNjorIuhZssSH9oH/E2j1+U9xf/oEg=="
        },
        {
            "id": "MEUCIQCoKZBUnUGEDPzlZTn8c8+lIi6g811YV5UMdapZHiTVoAIgKX21z0jv2M/m33OuC+Iem0zBQxCV6Vgjpb7TBoxpUlw="
        },
        {
            "id": "MEUCIQD4cJyI3r+Axx5BNS74qgRh+UEr8c6F+D1CqTQB/7xcsgIgGiq5mO+gFk8d0X3k+JDiiyc1tx6tjCxUKF0NiNwxWMA="
        },
        {
            "id": "MEUCIQD2RjBcoLjJWMlYTWyHomexu6cpDax3rwpYBIcEDFqQKgIgStuyjpydNFuLxhUCZplYsNG6N8gBRPy6tKrKYcdtrwE="
        },
        {
            "id": "MEUCIQDQuTViw8IfqV1YWLlSLIr5vfVUhnuyEK7DmkdpK7xnZgIgFSM0XMByd+w7u6d2pya/ZMtgD3vCc5RQE9Kk9O5zWhk="
        },
        {
            "id": "MEUCIQCFH6XDqfaGD2m8I+RdwsjC1f6fbCzReeL8itWar8o04AIgKAAP+GZdnjlH8GU4PjXe+qYQCFdEkqbCRzhLDIqts8g="
        },
        {
            "id": "MEUCIQCGOxLzuFVZF6ynTN5N7/ij2JGD7RJH4tqmbbRY0miuTwIgb+lkR9ijrSo2Zte+zxUJFCbPzciur47cGecSnZzO+1s="
        },
        {
            "id": "MEUCIQD9eZMURrSoICnO70Q8QLmly7vrfl+8L3fRe1xnjBi2fwIgNGbSU2gV7A9Zw7W5R+cAuO3CBHp/HycT/yl0TMFC7p4="
        },
        {
            "id": "MEQCIGZLyTLaHqIPyqS8dA0OjBvf2ORxabaqhuTNtg0LOZ80AiBuR6Z9sLDog/1XKZpC28VIg5TnW3cNfbeTgx2dMBa3Ag=="
        },
        {
            "id": "MEUCIQDKVQJmwgD2FBTw72/7WLya/+gDSMEWtMuWVpWt85vTLQIgP5L4G8/AcNjXbVBktjzbZQ0f1V5vdh6sm8aTKks1FVs="
        },
        {
            "id": "MEQCIDCxq7XKdFA+nI+n2kfDyqp43CnErjRZJ1YDvtiuYUfzAiAm3+3ArBuCPcbp1y75VzBu4gqzGMFVeMSxf9GjUhrVOA=="
        },
        {
            "id": "MEUCIQDmKjgNHyIjSXYeem4xPhszjayTJQQWZR3J4IRre2t4+gIgI54dJfNUnc3r0ezLHLAVo3uTmn6wdCDTZukwZZf08RM="
        },
        {
            "id": "MEQCIBYcsaI5MmWHEZb55nHS98TQw3129/cRgHk+7Qq1LEEoAiAvNMmifKURwXZRSc3rhxfGSWTnbbtsJf5Qp2ROVQShoA=="
        },
        {
            "id": "MEUCIQCxYK5ekc8G0crPUxI0sC0cVDWTZNpjrdafYrGpGJGf5QIgFAgfK3F0A9/F8+8xtPiWCDglliOL2dJ3TnNFNfum6p0="
        },
        {
            "id": "MEQCIBCLSEUQLLaVPeF+W/RPDIiufBd+DJPNpc/wPUfaB2MkAiB9hg5Ec5BX/Xj8WOJu3QDggJ4pYc5ZSPI03k8RSIvKXg=="
        },
        {
            "id": "MEUCIQDjCLDb8DHvjiEa5tE1REoyvxr+0KWIsoNxajujCw5SUgIgMlKCVbiNEcvBswR1vR+UlX/o008CpZERUUUfnT25u+8="
        },
        {
            "id": "MEQCIDOk0lVuyRQEFFfsgv8SnjuaYMQgvLWErvg5hQ5cNavNAiBLtbwIkV7BzI4nJJDTZZc1QojQr0O8oJwwGQOU6VrOOw=="
        },
        {
            "id": "MEQCICw1vHbdWSQn3g9JVtLS6tRD4v/Y4PAR5jLZgjX4uczRAiAbtdTTxecDX3jQ7bjMABGx5yFl0ixYjQJzkjkaiQiJsA=="
        },
        {
            "id": "MEUCIQDfWmrd9HRYg4JeqIXPC3jsfVi1dilIpJwMviOv5pHexAIgOOo0zexcWwA6RbLE7feYo6PT46k1zxz9NQ7ZhvDr79A="
        },
        {
            "id": "MEUCIQDYRztkTpjXXGKoGe4KeJMBLT80r8mG6jQ3zdm8Pjf56AIgFfcELoNnESZ6/PJcPE9xy33AecD5G3eLBcODpDY55M0="
        },
        {
            "id": "MEUCIQDKlkg/bxwnt8Q/3Xjd15TxuAfNyEcNzEHNDmM63IUcqQIgI7qE10/fhgsrO1rhrSvpCknNzvwUaih6UuLaV5UMneg="
        },
        {
            "id": "MEQCID6KFpUQWCGT9cVGUeg6hls4txPnSjownd4pvmKLBOH8AiBe6qRxvPkkKP6uEUbY5EGbvgwKkrJkdzn2mTRHTBVWsA=="
        },
        {
            "id": "MEUCIQCwxAyVSt+Hb6js81UZESObqPL27BTEUJYrvA8zvgMddwIgdcz6XBrlxB8nWBOOhRlvFQ/bCtC0IM0ePSNZwJgv4WY="
        },
        {
            "id": "MEQCIDyHcRHgoJlhnt1+T8Z4+8dYzKOgKxE+ZkisST4/I786AiB5dbex6ptZ2W+vSoSuxUQgzucrzYju+b+97XYvvquAeg=="
        },
        {
            "id": "MEQCIHLgNZutVa0EY1+CHNoKXrSPYu02GgtJdEoU2zQroBAzAiAs3BICXXSeuGKfFbwiswYCXWwWbo3jac1k7NjSBPUb0A=="
        },
        {
            "id": "MEUCIQCj4C0QCSfbOPg2InrjnFVOVLiKXoVEx5gH9Qgnim5CuQIgSe+w0qe5C8q7KrjmEzy0s335wrxmg327ts7RRrPdHy4="
        },
        {
            "id": "MEUCIQD2pcMkftB7nd6MhMrUUV26xk/vd1VQXxnGzox+s0BJPAIgHhV19lbJp4RYLyJ1O5LKHBpDkzENpwzQ04lk+1h7Z3Y="
        },
        {
            "id": "MEQCIBfjdh2sbzTaXLT5VO92c/gIwLfnAZxfcOieYlNbeGx/AiAiBpPcIEFQlZJcyyJC66zipQxkmj95tw8W1tldI0io9Q=="
        },
        {
            "id": "MEQCIFud+gQJbvmcWU1AnWDOQCHrDMSu01ps4naGSO9XXQesAiAAkFmEVExjYnNYLMXFf+Vj0vRGaqT1mT3tJoNZQHvK0A=="
        },
        {
            "id": "MEUCIQDpqGUZHNGrPNvEZi2Prr89wHIs5Vrb3miSWBBR09I3OwIgUppfyS7r6tmJ9diLuF8fT7RsmAevR+0QpemW6K4cVlE="
        },
        {
            "id": "MEUCIQDgQIkgSrGPYionwDCJkKr4PHO29usGaFkWLMSN94Jv/QIgRdiUeBs2yqmuvjfmZM/06uYm0cDTVusV0v+Xn8BW+xo="
        },
        {
            "id": "MEQCIEaW5AguNSowEqvOpZN+joAc2ohAq8BKQhpXKsfRpOZAAiBtnREj34DTY1XJGM2bI5MZq/nwM66XepAMzHbix1at1g=="
        },
        {
            "id": "MEUCIQCog8mJCQuTSGay/4dGhVkHmKIAn44s6u+OGQMSa0uPpAIgNvXeUcf2kQtUtjZ7wsNFEdFzFExRSiQ9w2FlUZ0GyhY="
        },
        {
            "id": "MEUCIQDbavZ9LbH7gyy4/Gqg6Ajp91phnriECCgjG22kk4ZFFAIgVGea5FrsfTEEqzPwO1TH6t80lojXSMfnZIu1mdE5/cc="
        },
        {
            "id": "MEUCIQCsxGnXby9Os7/RZBbLyDM7cOtrP3vs8Vt72RT1mBIWkgIgZKhN2BKgoj0g5RI6wg6atVh/36kCtX4FWHxZEvWtneA="
        },
        {
            "id": "MEUCIQDFrOvdDhGr1znkVHGJ9JRQrkZcop2L5Qj8vl2pIr2LnAIgXR9gHuV0GvpizacQhIqImP7LPO9yo5/aL/fqpitL7AM="
        },
        {
            "id": "MEUCIQCkkLSkbmeiIxpdbSA1S9zhpWMOIvx0UHIDNIiMLljiqQIgb0WBGt3Ixji3T69bhBL91qNklxwMhRz4VqE/bZhX1Gk="
        },
        {
            "id": "MEQCIEcNnSueCubgYk/gpzuVNaFv1GCPTo+XCjrpi1igJsb3AiB/y7LI1Uqoqdy3NT74q+/IF84JJUrYPPyRL9UBNX16Qg=="
        },
        {
            "id": "MEQCIDqgRGrgzHT/k74RfCDViFpaCFZA0o76IH14ZKVY7OfZAiBMFTpyXhgSeQQIUGf0bT92xHJ9qpkpaRaxFKD5VX8UnA=="
        },
        {
            "id": "MEQCIHXa5MD07lhppgUzccc6m1hzEm8iMhWZCqmjGIBgz7QkAiBZ2ZFJ5r4aq4Qad3PhXkS91p80Y2olXbwohVIIqlIGCg=="
        },
        {
            "id": "MEUCIQDEHrK9vX6xv9K6K0cYyzylldmu7PGRlNUN1Inys7Qo+AIgZK3e+5P6+ByENFPakUrHPT0DUuVO2ZgiO+gHIQA72bM="
        },
        {
            "id": "MEQCIEyD2MVStkEJjSs7+a4OErAm60juJ8LuXbo/47ko++FfAiBhRowDncFDXViB0XnNN59VMi3nBUtOUCGkqDiy1majcA=="
        },
        {
            "id": "MEUCIQDAAsbaZhXNIln4KV1GNkfgBX/TcOdya5YSVSZzhJr2lAIgRNH8IA6PqyMV2+qmkW/qtYSJT0L6oeOH/ix7dRkuWag="
        },
    ],
    "outputs": [
        {
            "to": "1L7JseLALwWrnzbwW4hsAh52U1n3VUD1Sy",
            "value": 49999.99,
        },
        {
            "to": "1E5NnE1MUxFFdK2mrCgif7Nucs1ohyLBkw",
            "value": 343.1161698349533,
        },
    ],
}

block = {
    "version": 5,
    "time": 1634248889,
    "index": 232286,
    "public_key": "02fa9550f57055c96c7ce4c6c9cd1411856beba5c7d5a07417e980a39aa03da3dc",
    "prevHash": "938bdfbcc2154ece061d46e8e4442f0897bc2e7558b7e855ab705f930e000000",
    "nonce": "628b217d32356464313266366332343036",
    "transactions": [
        txn,
        {
            "time": "1634248890",
            "rid": "",
            "id": "MEUCIQCbXTEPRp+0cb80gxjOAharft7JCCMjIW0vZDXhR5t59QIgVsFeqs0b5QwXRd6S4/cemjwLIMl7cr+MjosdZeDApo4=",
            "relationship": "",
            "public_key": "02fa9550f57055c96c7ce4c6c9cd1411856beba5c7d5a07417e980a39aa03da3dc",
            "dh_public_key": "",
            "fee": 0.0,
            "hash": "1f35c1b5564a901d4d1c6e6aba156815c3cfffa42fbf705557495f0e01293ff0",
            "inputs": [],
            "outputs": [{"to": "13AYDe1jxvYdAFcrUUKGGNC2ZbECXuN5KK", "value": 25.0}],
        },
    ],
    "hash": "456a12375ca2b453bff22e89bfc6eae577a125e20865e7316b2e3fff02000000",
    "merkleRoot": "07f10db81f4544611f985fdcc30cef4479ea9d046c0a67e8c9abc89ada303ee6",
    "special_min": False,
    "target": "0000002dfd66dc3ed3d200000000000000000000000000000000000000000000",
    "special_target": "0000002dfd66dc3ed3d200000000000000000000000000000000000000000000",
    "header": "5163424888902fa9550f57055c96c7ce4c6c9cd1411856beba5c7d5a07417e980a39aa03da3dc232286938bdfbcc2154ece061d46e8e4442f0897bc2e7558b7e855ab705f930e000000{nonce}0000002dfd66dc3ed3d20000000000000000000000000000000000000000000007f10db81f4544611f985fdcc30cef4479ea9d046c0a67e8c9abc89ada303ee6",
    "id": "MEUCIQDVQKsWTCc5TeAk8PoFUGDqYUyLXWp8pfANz40qvCMF7gIgb0MrEze0XfvD7KBGj86f12A4m4AHauCziwSEY7ny0dg=",
    "updated_at": 1634249056.5414934,
}


async def mock_get_unspent_txns(self, query):
    async def get_txn():
        yield {
            "transactions": {
                "id": "MEUCIQDAAsbaZhXNIln4KV1GNkfgBX/TcOdya5YSVSZzhJr2lAIgRNH8IA6PqyMV2+qmkW/qtYSJT0L6oeOH/ix7dRkuWag=",
                "outputs": {"to": "1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4", "value": 1},
            }
        }

    return get_txn()


async def mock_get_mempool_transactions(self, input_ids, public_key):
    async def get_txn():
        yield True

    return get_txn()


class TestBlockchainUtils(AsyncTestCase):
    @mock.patch(
        "yadacoin.core.blockchain.Blockchain.mongo", new_callable=lambda: MongoClient
    )
    async def asyncSetUp(self, mongo):
        mongo.async_db = mock.MagicMock()
        mongo.async_db.blocks = mock.MagicMock()
        yadacoin.core.config.CONFIG = Config.generate()
        Config().mongo = mongo

    async def setBlock(self):
        self.block = await Block.from_dict(block)

    async def test_is_input_spent(self):
        NodeApplication(test=True)
        config = Config()
        await self.setBlock()
        start = time.time()
        await config.BU.is_input_spent(
            [x.id for x in self.block.transactions[0].inputs],
            self.block.transactions[1].public_key,
        )
        duration = time.time() - start
        config.app_log.info(f"Duration: {duration}")

    @patch(
        "yadacoin.core.blockchainutils.BlockChainUtils.get_unspent_txns",
        new=mock_get_unspent_txns,
    )
    @patch(
        "yadacoin.core.blockchainutils.BlockChainUtils.get_mempool_transactions",
        new=mock_get_mempool_transactions,
    )
    async def test_get_wallet_unspent_transactions_mempool(self):
        NodeApplication(test=True)
        config = Config()

        genesis_block = await Blockchain.get_genesis_block()
        await genesis_block.save()
        res = [
            x["id"]
            async for x in config.BU.get_wallet_unspent_transactions_for_spending(
                "1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4", 5, inc_mempool=False
            )
        ]
        self.assertTrue(len(res) > 0)
        self.assertTrue(
            "MEUCIQDAAsbaZhXNIln4KV1GNkfgBX/TcOdya5YSVSZzhJr2lAIgRNH8IA6PqyMV2+qmkW/qtYSJT0L6oeOH/ix7dRkuWag="
            in res
        )

        res2 = [
            x["id"]
            async for x in config.BU.get_wallet_unspent_transactions_for_spending(
                "1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4", 5, inc_mempool=True
            )
        ]
        print(res2)
        self.assertFalse(
            "MEUCIQDAAsbaZhXNIln4KV1GNkfgBX/TcOdya5YSVSZzhJr2lAIgRNH8IA6PqyMV2+qmkW/qtYSJT0L6oeOH/ix7dRkuWag="
            in res2
        )

    async def test_get_wallet_balance(self):
        NodeApplication(test=True)
        config = Config()
        config.database = hashlib.sha256(str(time.time()).encode()).hexdigest()[:10]
        config.mongo = Mongo()
        genesis_block = await Blockchain.get_genesis_block()
        await config.mongo.async_db.blocks.insert_one(genesis_block.to_dict())

        spend_block = await Block.from_dict(
            {
                "merkleRoot": "c816fe62ee6c883226cb8dad100d9338963544c5d9fe8384c5b0be9aaf0cd961",
                "time": 1537979085,
                "special_min": False,
                "index": 11356,
                "version": 1,
                "target": "0000003fffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
                "public_key": "02a9225bc5deb4d66262c34cfe3e40c7ba3ff12768540e9b69729978b850a3cabb",
                "hash": "00000027175a9dde28a7b26517b026a7866ddb1cfcceaa3627558b5931a1e6c3",
                "nonce": 14636080,
                "transactions": [
                    {
                        "dh_public_key": "",
                        "outputs": [
                            {"to": "12Aa9hfgnapHgd6KhRu2HPvMLfWXDprwAQ", "value": 1.0},
                            {"to": "1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4", "value": 48.99},
                        ],
                        "hash": "6329037c7b8de1e19555cb3059c2a2bdccb6e417bc7ec63cdc4bc55b40320af4",
                        "relationship": "",
                        "id": "MEQCIEeaAcF7erg/5Uvso5K5J1TrCS+ThWF52waBwh8+/ZhKAiAHnECJe8ASmIF6/SG/TRKCCq558GLb2Jc6TN/QEElMOw==",
                        "fee": 0.01,
                        "inputs": [
                            {
                                "id": "MEUCIQCJrtJ/IXFgdU1vKNHeKMq7SYSkLt4Jv/v1p1AFN9jMEAIgI0u/51Syn8Ee4/41UEDgUYOCDiDq+mlMtjAObedD9WM="
                            }
                        ],
                        "public_key": "03f44c7c4dca3a9204f1ba284d875331894ea8ab5753093be847d798274c6ce570",
                        "rid": "",
                    },
                    {
                        "dh_public_key": "",
                        "outputs": [
                            {"to": "16bcSsSiZLdb5VDZnoCYj3DRLh5Ea9Usp1", "value": 50.01}
                        ],
                        "hash": "9009bdec2f428652ea84bef8dff253ab01c6139b6d1ed6460ea3b17818e4e71a",
                        "relationship": "",
                        "id": "MEQCIFznbYk6d3En+f9SRZfEBWU7Hj3zRpRY+3d8ZqNQ+/b1AiBJNQeC/oBv533Lta3QYElsz2Ai3IBEETZRwVaZdw3xPw==",
                        "fee": 0.0,
                        "inputs": [],
                        "public_key": "02a9225bc5deb4d66262c34cfe3e40c7ba3ff12768540e9b69729978b850a3cabb",
                        "rid": "",
                    },
                ],
                "id": "MEQCIFChEOyOTkWmSGp9fkXo6VJ6DJ+//gmEk68ZW8503gKhAiB6RQYV4XLPFzLjP8ESQ3k/CRDRRb8w9P80QW/G8BmcAw==",
                "header": "",
                "prevHash": "00000000c7dc961a0b86785fdd68298fc2bfcfffe86a8a343e6e6feb33916c5c",
                "updated_at": 1.5724002324503367e9,
            }
        )
        await config.mongo.async_db.blocks.replace_one(
            {"id": spend_block.signature}, spend_block.to_dict()
        )
        total_received_balance = await config.BU.get_total_output_balance(
            "1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4"
        )
        self.assertTrue(total_received_balance > 0)

        total_spent_balance = await config.BU.get_spent_balance(
            "1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4"
        )
        self.assertTrue(total_spent_balance > 0)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
