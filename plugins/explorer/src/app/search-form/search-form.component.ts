import { Component, OnInit } from "@angular/core";
import { Http } from "@angular/http";
import { Search } from "../search";

declare var Bitcoin;

function makeUrl(url) {
  if (window.location.hostname === "localhost") {
    return "http://localhost:8005" + url;
  }
  return url;
}

@Component({
  selector: "app-search-form",
  templateUrl: "./search-form.component.html",
  styleUrls: ["./search-form.component.css"],
})
export class SearchFormComponent implements OnInit {
  model = new Search("");
  result = [];
  resultType = "";
  balance = 0;
  searching = false;
  submitted = false;
  current_height = "";
  circulating = "";
  hashrate = "";
  difficulty = "";
  expertMode = false;
  mempoolView = false;
  mempoolTransactions = [];
  mempoolPage = 1;
  mempoolPageSize = 25;
  mempoolTotal = 0;
  mempoolLoading = false;

  constructor(public http: Http) {
    this.http.get(makeUrl("/api-stats")).subscribe(
      (res: any) => {
        this.difficulty = this.numberWithCommas(
          res.json()["stats"]["difficulty"],
        );
        this.hashrate = this.numberWithCommas(
          res.json()["stats"]["network_hash_rate"],
        );
        this.current_height = this.numberWithCommas(
          res.json()["stats"]["height"],
        );
        this.circulating = this.numberWithCommas(
          res.json()["stats"]["circulating"],
        );
        if (!window.location.search) {
          this.http
            .get(
              makeUrl(
                "/explorer-search?term=" + this.current_height.replace(",", ""),
              ),
            )
            .subscribe(
              (res: any) => {
                this.result = res.json().result || [];
                this.resultType = res.json().resultType;
                this.balance = res.json().balance;
                this.searching = false;
              },
              (err: any) => {
                alert("something went terribly wrong!");
              },
            );
        }
      },
      (err: any) => {
        alert("something went terribly wrong!");
      },
    );
    if (window.location.search) {
      const params = new URLSearchParams(window.location.search);
      const term = params.get("term");
      if (term) {
        this.model.term = term;
      }
      this.searching = true;
      this.submitted = true;
      this.http
        .get(makeUrl("/explorer-search" + window.location.search))
        .subscribe(
          (res: any) => {
            this.result = res.json().result || [];
            this.resultType = res.json().resultType;
            this.balance = res.json().balance;
            this.searching = false;
          },
          (err: any) => {
            alert("something went terribly wrong!");
          },
        );
    }
  }

  ngOnInit() {}

  onSubmit() {
    this.searching = true;
    this.submitted = true;
    this.http
      .get(
        makeUrl("/explorer-search?term=" + encodeURIComponent(this.model.term)),
      )
      .subscribe(
        (res: any) => {
          this.result = res.json().result || [];
          this.resultType = res.json().resultType;
          this.balance = res.json().balance;
          this.searching = false;
        },
        (err: any) => {
          alert("something went terribly wrong!");
        },
      );
  }

  numberWithCommas(x) {
    return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }

  // TODO: Remove this when we're done
  get diagnostic() {
    return JSON.stringify(this.model);
  }

  encodeAddress(publicKeyHex) {
    const bitcoin = Bitcoin;
    const pubkey = Bitcoin.ECPubKey(
      Bitcoin.convert.hexToBytes(publicKeyHex),
      true,
    );
    return pubkey.getAddress().toString();
  }

  get mempoolTotalPages() {
    return Math.max(1, Math.ceil(this.mempoolTotal / this.mempoolPageSize));
  }

  viewMempool() {
    this.mempoolView = !this.mempoolView;
    if (this.mempoolView && this.mempoolTransactions.length === 0) {
      this.loadMempoolPage(1);
    }
  }

  loadMempoolPage(page: number) {
    if (page < 1 || page > this.mempoolTotalPages) { return; }
    this.mempoolPage = page;
    this.mempoolLoading = true;
    this.http
      .get(makeUrl(`/get-mempool?page=${page}&page_size=${this.mempoolPageSize}`))
      .subscribe(
        (res: any) => {
          const data = res.json();
          this.mempoolTransactions = data.transactions || [];
          this.mempoolTotal = data.total || 0;
          this.mempoolLoading = false;
        },
        (err: any) => {
          this.mempoolLoading = false;
          alert('Failed to load mempool!');
        },
      );
  }
}
